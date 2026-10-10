// Living Assistant desktop shell: the floating agent (orb + chat panel) that stays on top of
// the desktop, independent of any browser. It keeps the local backend running, remembers
// where you put it, lives in the system tray and can start with the OS.
const { app, BrowserWindow, desktopCapturer, ipcMain, screen, globalShortcut, Tray, Menu, nativeImage, shell, dialog } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const http = require('http')
const path = require('path')

if (!app.requestSingleInstanceLock()) {
  app.quit()  // another copy is already running; it gets a 'second-instance' event instead
} else {
  main()
}

function main() {
  const API_URL = (process.env.ASSISTANT_API_URL || 'http://127.0.0.1:8787').replace(/\/$/, '')
  const PROJECT_ROOT = path.resolve(__dirname, '..')
  const SIZE = { collapsed: { w: 380, h: 320 }, expanded: { w: 440, h: 720 } }
  const settingsFile = () => path.join(app.getPath('userData'), 'agent-settings.json')

  let agentWin = null
  let tray = null
  let expanded = false
  let backendChild = null
  let settings = loadSettings()

  function loadSettings() {
    try { return JSON.parse(fs.readFileSync(settingsFile(), 'utf8')) } catch (_) { return {} }
  }
  function saveSettings(patch) {
    settings = { ...settings, ...patch }
    try {
      fs.mkdirSync(path.dirname(settingsFile()), { recursive: true })
      fs.writeFileSync(settingsFile(), JSON.stringify(settings, null, 2))
    } catch (_) {}
  }

  // ---- window placement: remembered by the orb's corner (bottom-right of the window) ----

  // The orb's centre sits ORB px in from the window's bottom-right corner (.desk-dock is
  // 200x200 at the corner with a 64px face). Collapsed, the transparent part of the window
  // may hang off-screen but the whole face stays visible and reachable; expanded, the chat
  // panel stays fully inside the work area.
  const ORB = 100, HALF = 32, PAD = 8

  function clampToDisplay(right, bottom, w, h) {
    const display = screen.getDisplayNearestPoint({ x: Math.round(right - ORB), y: Math.round(bottom - ORB) })
    const area = display.workArea
    const collapsed = w === SIZE.collapsed.w && h === SIZE.collapsed.h
    const overhang = collapsed ? ORB - HALF - PAD : 0
    const minRight = collapsed ? ORB + HALF + PAD : Math.min(w, area.width)
    const minBottom = collapsed ? ORB + HALF + PAD : Math.min(h, area.height)
    const r = Math.min(Math.max(right, area.x + minRight), area.x + area.width + overhang)
    const b = Math.min(Math.max(bottom, area.y + minBottom), area.y + area.height + overhang)
    let x = Math.round(r - w), y = Math.round(b - h)
    if (y < area.y) y = area.y  // an expanded panel never goes above the top of the screen
    return { x, y, width: w, height: h }
  }

  function anchor() {
    if (agentWin && !agentWin.isDestroyed()) {
      const b = agentWin.getBounds()
      return { right: b.x + b.width, bottom: b.y + b.height }
    }
    const area = screen.getPrimaryDisplay().workArea
    if (Number.isFinite(settings.right) && Number.isFinite(settings.bottom)) return { right: settings.right, bottom: settings.bottom }
    return { right: area.x + area.width - 8, bottom: area.y + area.height - 8 }
  }

  let expandAnchor = null  // the orb's corner when the panel opened: collapsing returns exactly there
  function applySize() {
    if (!agentWin || agentWin.isDestroyed()) return
    const { w, h } = expanded ? SIZE.expanded : SIZE.collapsed
    if (expanded && !expandAnchor) expandAnchor = anchor()
    const { right, bottom } = expanded ? expandAnchor : (expandAnchor || anchor())
    if (!expanded) expandAnchor = null
    agentWin.setBounds(clampToDisplay(right, bottom, w, h), false)
  }

  function rememberPosition() {
    if (!agentWin || agentWin.isDestroyed()) return
    const b = agentWin.getBounds()
    saveSettings({ right: b.x + b.width, bottom: b.y + b.height })
  }

  // ---- the floating agent window ----------------------------------------------------

  function createAgentWindow() {
    const { right, bottom } = anchor()
    agentWin = new BrowserWindow({
      ...clampToDisplay(right, bottom, SIZE.collapsed.w, SIZE.collapsed.h),
      frame: false,
      transparent: true,
      resizable: false,
      movable: true,
      minimizable: false,
      maximizable: false,
      fullscreenable: false,
      skipTaskbar: true,
      hasShadow: false,
      alwaysOnTop: true,
      show: false,
      backgroundColor: '#00000000',
      webPreferences: {
        preload: path.join(__dirname, 'agent-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    })
    // 'screen-saver' is the highest z-level; 'floating' drops behind fullscreen apps on Windows.
    agentWin.setAlwaysOnTop(true, 'screen-saver')
    agentWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
    agentWin.setIgnoreMouseEvents(true, { forward: true })
    agentWin.once('ready-to-show', () => agentWin.showInactive())

    // Only the local agent page may load here; anything else opens in the browser.
    agentWin.webContents.on('will-navigate', (event, url) => {
      if (!url.startsWith(`${API_URL}/agent`)) { event.preventDefault(); shell.openExternal(url) }
    })
    agentWin.webContents.setWindowOpenHandler(({ url }) => {
      if (/^https?:\/\//.test(url)) shell.openExternal(url)
      return { action: 'deny' }
    })

    const load = () => { if (agentWin && !agentWin.isDestroyed()) agentWin.loadURL(`${API_URL}/agent`) }
    // The backend may still be starting; keep retrying until it answers.
    agentWin.webContents.on('did-fail-load', () => setTimeout(load, 3000))
    load()

    const cursorTimer = setInterval(() => {
      if (!agentWin || agentWin.isDestroyed()) return clearInterval(cursorTimer)
      if (agentWin.isVisible()) agentWin.webContents.send('agent-cursor', screen.getCursorScreenPoint())
    }, 50)
    // Fullscreen apps re-raise themselves when focused and can cover other topmost windows;
    // put the agent back on top without taking focus.
    const topTimer = setInterval(() => {
      if (!agentWin || agentWin.isDestroyed()) return clearInterval(topTimer)
      if (agentWin.isVisible() && !agentWin.isFocused()) agentWin.moveTop()
    }, 1500)
    agentWin.on('moved', rememberPosition)
    agentWin.on('closed', () => { clearInterval(cursorTimer); clearInterval(topTimer); agentWin = null })
  }

  function showAgent() {
    if (!agentWin || agentWin.isDestroyed()) createAgentWindow()
    else agentWin.showInactive()
  }

  function sendAction(action) {
    showAgent()
    if (agentWin && !agentWin.isDestroyed()) agentWin.webContents.send('agent-menu-action', action)
  }

  function openDashboard() { shell.openExternal(`${API_URL}/dashboard`) }

  // ---- kill switch: stop everything the assistant is doing, shut the backend down, quit ----
  // The page holds the API token, so it asks the backend to halt and exit; the shell quits
  // right after, or on its own if the backend does not answer in time.
  let killing = false
  function killSwitch({ confirm = true } = {}) {
    if (killing) return
    if (confirm) {
      const choice = dialog.showMessageBoxSync({
        type: 'warning', buttons: ['Stop everything and quit', 'Cancel'], defaultId: 1, cancelId: 1,
        title: 'Kill switch', message: 'Stop the assistant completely?',
        detail: 'Running chats and background goals are cancelled, models and processes are stopped, and the assistant quits.',
      })
      if (choice !== 0) return
    }
    killing = true
    if (agentWin && !agentWin.isDestroyed()) agentWin.webContents.send('agent-menu-action', 'kill')
    setTimeout(() => app.quit(), 5000)
  }

  // The backend writes this file when the kill switch shuts it down (from the dashboard, the chat
  // or here); the shell then quits too, and stops supervising so nothing restarts.
  const killMarker = path.join(require('os').tmpdir(), 'LivingAssistant', 'killed.json')
  const startedAt = Date.now()
  setInterval(() => {
    try {
      if (fs.statSync(killMarker).mtimeMs > startedAt && !killing) { killing = true; app.quit() }
    } catch (_) {}
  }, 1500)

  // ---- IPC from the agent page ------------------------------------------------------

  ipcMain.handle('agent-move', (_event, dx, dy) => {
    if (!agentWin || agentWin.isDestroyed()) return false
    const b = agentWin.getBounds()
    agentWin.setBounds(clampToDisplay(b.x + b.width + dx, b.y + b.height + dy, b.width, b.height), false)
    return true
  })
  // Dragging follows the real cursor position: the window is placed where the cursor is now
  // (minus where it grabbed the orb), so moves never pile up or lag behind.
  let dragOffset = null
  ipcMain.handle('agent-drag-start', () => {
    if (!agentWin || agentWin.isDestroyed()) return false
    const b = agentWin.getBounds(), p = screen.getCursorScreenPoint()
    dragOffset = { x: p.x - (b.x + b.width), y: p.y - (b.y + b.height) }
    return true
  })
  ipcMain.handle('agent-drag-move', () => {
    if (!dragOffset || !agentWin || agentWin.isDestroyed()) return false
    const b = agentWin.getBounds(), p = screen.getCursorScreenPoint()
    agentWin.setBounds(clampToDisplay(p.x - dragOffset.x, p.y - dragOffset.y, b.width, b.height), false)
    return true
  })
  ipcMain.handle('agent-drag-end', () => { dragOffset = null; rememberPosition(); return true })
  ipcMain.handle('agent-save-position', () => { rememberPosition(); return true })
  ipcMain.handle('agent-click-through', (_event, on) => {
    if (!agentWin || agentWin.isDestroyed()) return false
    agentWin.setIgnoreMouseEvents(Boolean(on), { forward: true })
    return true
  })
  ipcMain.handle('agent-expand', (_event, on) => {
    expanded = Boolean(on)
    applySize()
    if (expanded && agentWin) { agentWin.setIgnoreMouseEvents(false); agentWin.focus() }  // typing needs focus
    return true
  })
  ipcMain.handle('agent-open-dashboard', () => { openDashboard(); return true })
  ipcMain.handle('agent-quit', () => { killing = true; setTimeout(() => app.quit(), 200); return true })
  // Screen capture for "ask about my screen": the agent hides itself so it is not in the picture.
  ipcMain.handle('agent-capture-screen', async (event) => {
    if (!agentWin || agentWin.isDestroyed() || event.sender !== agentWin.webContents) return null
    const display = screen.getDisplayMatching(agentWin.getBounds())
    const size = { width: Math.round(display.size.width * display.scaleFactor), height: Math.round(display.size.height * display.scaleFactor) }
    agentWin.hide()
    try {
      await new Promise((resolve) => setTimeout(resolve, 250))
      const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: size })
      const source = sources.find((s) => String(s.display_id) === String(display.id)) || sources[0]
      return source && !source.thumbnail.isEmpty() ? source.thumbnail.toDataURL() : null
    } finally {
      agentWin.showInactive()
      agentWin.focus()
    }
  })
  ipcMain.handle('agent-menu', (_event, opts) => {
    if (!agentWin || agentWin.isDestroyed()) return false
    Menu.buildFromTemplate([
      { label: expanded ? 'Close chat' : 'Open chat', click: () => sendAction('toggle-chat') },
      { label: 'Talk (voice)', click: () => sendAction('talk') },
      { label: 'Speak replies', type: 'checkbox', checked: Boolean(opts && opts.speakReplies), click: () => sendAction('toggle-speak') },
      { type: 'separator' },
      { label: 'Open Dashboard', click: openDashboard },
      { label: 'Start with Windows', type: 'checkbox', checked: launchAtLogin(), click: (item) => setLaunchAtLogin(item.checked), visible: process.platform !== 'linux' },
      { label: 'Hide floating agent', click: () => agentWin && agentWin.hide() },
      { type: 'separator' },
      { label: 'Kill switch - stop everything', accelerator: 'CommandOrControl+Alt+Shift+K', click: () => killSwitch() },
    ]).popup({ window: agentWin })
    return true
  })

  // ---- launch with the OS (opt-in) ------------------------------------------------------

  function loginArgs() { return app.isPackaged ? [] : [path.resolve(__dirname)] }
  function launchAtLogin() {
    try { return app.getLoginItemSettings({ args: loginArgs() }).openAtLogin } catch (_) { return false }
  }
  function setLaunchAtLogin(on) {
    try { app.setLoginItemSettings({ openAtLogin: Boolean(on), path: process.execPath, args: loginArgs() }) } catch (_) {}
    buildTray()
  }

  // ---- backend supervisor ---------------------------------------------------------------
  // run.bat starts the backend itself; after a login start or a crash the shell starts it
  // (hidden) so the agent keeps working. Only a backend this shell started is stopped by it.

  function backendUp() {
    return new Promise((resolve) => {
      const req = http.get(`${API_URL}/agent`, { timeout: 2500 }, (res) => { res.resume(); resolve(res.statusCode < 500) })
      req.on('error', () => resolve(false))
      req.on('timeout', () => { req.destroy(); resolve(false) })
    })
  }

  function pythonPath() {
    if (process.env.ASSISTANT_PYTHON) return process.env.ASSISTANT_PYTHON
    const venv = process.platform === 'win32' ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe') : path.join(PROJECT_ROOT, '.venv', 'bin', 'python')
    return fs.existsSync(venv) ? venv : null
  }

  function startBackend() {
    const python = pythonPath()
    if (!python || backendChild) return false
    const port = new URL(API_URL).port || '8787'
    const logDir = path.join(app.getPath('userData'), 'logs')
    fs.mkdirSync(logDir, { recursive: true })
    const log = fs.openSync(path.join(logDir, 'backend.log'), 'a')
    backendChild = spawn(python, ['-m', 'uvicorn', 'living_assistant.api:app', '--host', '127.0.0.1', '--port', port], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, PYTHONPATH: path.join(PROJECT_ROOT, 'src'), PYTHONUNBUFFERED: '1', PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
      windowsHide: true,
      stdio: ['ignore', log, log],
    })
    backendChild.on('exit', () => { backendChild = null })
    return true
  }

  let downSince = null
  let backoff = 5000
  async function superviseBackend() {
    const up = await backendUp()
    if (up) {
      downSince = null
      backoff = 5000
    } else {
      downSince = downSince || Date.now()
      // Give an external launcher (run.bat) a head start before starting our own backend.
      if (!killing && !backendChild && Date.now() - downSince > 8000 && settings.superviseBackend !== false) {
        if (startBackend()) backoff = Math.min(backoff * 2, 120000)
      }
    }
    setTimeout(superviseBackend, up ? 5000 : backoff)
  }

  // ---- tray -------------------------------------------------------------------------------

  function buildTray() {
    const image = nativeImage.createFromPath(path.join(PROJECT_ROOT, 'passistant.png'))
    if (!tray) {
      tray = new Tray(image.isEmpty() ? nativeImage.createEmpty() : image.resize({ width: 16, height: 16 }))
      tray.setToolTip('Living Assistant')
      tray.on('click', () => sendAction('open-chat'))
    }
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: 'Open chat', click: () => sendAction('open-chat') },
      { label: 'Talk (voice)', click: () => sendAction('talk') },
      { label: 'Show floating agent', click: showAgent },
      { label: 'Hide floating agent', click: () => agentWin && agentWin.hide() },
      { label: 'Open Dashboard', click: openDashboard },
      { type: 'separator' },
      { label: 'Start with Windows', type: 'checkbox', checked: launchAtLogin(), click: (item) => setLaunchAtLogin(item.checked), visible: process.platform !== 'linux' },
      { label: 'Kill switch - stop everything', click: () => killSwitch() },
      { label: 'Quit', click: () => app.quit() },
    ]))
  }

  app.on('second-instance', () => sendAction('open-chat'))

  app.whenReady().then(() => {
    createAgentWindow()
    buildTray()
    superviseBackend()
    globalShortcut.register('CommandOrControl+Shift+Space', () => sendAction('toggle-chat'))
    // Emergency stop from anywhere, no confirmation.
    globalShortcut.register('CommandOrControl+Alt+Shift+K', () => killSwitch({ confirm: false }))
    // A monitor unplugged or rescaled: bring the orb back onto a screen that still exists.
    const replace = () => { applySize(); rememberPosition() }
    screen.on('display-removed', replace)
    screen.on('display-metrics-changed', replace)
  })

  // The agent lives in the tray: closing windows does not quit the app.
  app.on('window-all-closed', () => {})
  app.on('will-quit', () => {
    globalShortcut.unregisterAll()
    if (backendChild) { try { backendChild.kill() } catch (_) {} }
  })
}
