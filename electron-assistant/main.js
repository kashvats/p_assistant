const { app, BrowserWindow, ipcMain, screen, powerMonitor, globalShortcut, Tray, Menu, nativeImage } = require('electron')
const path = require('path')

let tray = null
let agentWin = null
let mainWin = null

const API_URL = process.env.ASSISTANT_API_URL || 'http://127.0.0.1:8787'
const AGENT_W = 380
const AGENT_H = 320

function openDashboard() {
  require('electron').shell.openExternal(`${API_URL}/dashboard`)
}

function showAgent() {
  if (!agentWin || agentWin.isDestroyed()) createAgentWindow()
  else agentWin.showInactive()
}

// The floating agent: a small transparent, always-on-top window whose empty
// areas pass clicks through to the desktop. It loads /agent from the local API.
function createAgentWindow() {
  const { workArea } = screen.getPrimaryDisplay()
  agentWin = new BrowserWindow({
    width: AGENT_W,
    height: AGENT_H,
    x: workArea.x + workArea.width - AGENT_W - 8,
    y: workArea.y + workArea.height - AGENT_H - 8,
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

  // Only the local agent page may load here; anything else opens in the browser.
  agentWin.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(`${API_URL}/agent`)) { event.preventDefault(); require('electron').shell.openExternal(url) }
  })
  agentWin.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(API_URL)) require('electron').shell.openExternal(url)
    return { action: 'deny' }
  })

  const load = () => { if (agentWin && !agentWin.isDestroyed()) agentWin.loadURL(`${API_URL}/agent`) }
  // The API may still be starting (run.bat launches both); keep retrying until it answers.
  agentWin.webContents.on('did-fail-load', () => setTimeout(load, 3000))
  load()

  const cursorTimer = setInterval(() => {
    if (!agentWin || agentWin.isDestroyed()) return clearInterval(cursorTimer)
    if (agentWin.isVisible()) agentWin.webContents.send('agent-cursor', screen.getCursorScreenPoint())
  }, 50)
  // Fullscreen apps (browsers, players) re-raise themselves when focused and can
  // cover other topmost windows; put the agent back on top without taking focus.
  const topTimer = setInterval(() => {
    if (!agentWin || agentWin.isDestroyed()) return clearInterval(topTimer)
    if (agentWin.isVisible() && !agentWin.isFocused()) agentWin.moveTop()
  }, 1500)
  agentWin.on('closed', () => { clearInterval(cursorTimer); clearInterval(topTimer); agentWin = null })
}

ipcMain.handle('agent-move', (_event, dx, dy) => {
  if (!agentWin || agentWin.isDestroyed()) return false
  const [x, y] = agentWin.getPosition()
  // Keep the orb (bottom-right of the window) on some screen.
  const display = screen.getDisplayNearestPoint({ x: x + AGENT_W - 100, y: y + AGENT_H - 100 })
  const area = display.workArea
  const nx = Math.min(Math.max(x + dx, area.x - AGENT_W + 170), area.x + area.width - 170)
  const ny = Math.min(Math.max(y + dy, area.y - AGENT_H + 170), area.y + area.height - 170)
  agentWin.setPosition(Math.round(nx), Math.round(ny), false)
  return true
})

ipcMain.handle('agent-click-through', (_event, on) => {
  if (!agentWin || agentWin.isDestroyed()) return false
  agentWin.setIgnoreMouseEvents(Boolean(on), { forward: true })
  return true
})

ipcMain.handle('agent-menu', (_event, opts) => {
  if (!agentWin || agentWin.isDestroyed()) return false
  Menu.buildFromTemplate([
    { label: 'Open Dashboard', click: openDashboard },
    { label: 'Speak replies', type: 'checkbox', checked: Boolean(opts && opts.speakReplies),
      click: () => agentWin && agentWin.webContents.send('agent-menu-action', 'toggle-speak') },
    { label: 'Show Assistant window', click: showAssistant },
    { type: 'separator' },
    { label: 'Hide floating agent', click: () => agentWin && agentWin.hide() },
  ]).popup({ window: agentWin })
  return true
})

function showAssistant() {
 if (!mainWin || mainWin.isDestroyed()) createWindow()
 mainWin.show()
 mainWin.focus()
}

function hideAssistant() {
 const win = mainWin
 if (win) win.hide()
}

function createTray() {
 if (tray) return
 const image = nativeImage.createFromPath(path.join(__dirname, '..', 'passistant.png'))
 tray = new Tray(image.isEmpty() ? nativeImage.createEmpty() : image)
 tray.setToolTip('Living Assistant')
 tray.setContextMenu(Menu.buildFromTemplate([
   { label: 'Show Assistant', click: showAssistant },
   { label: 'Hide Assistant', click: hideAssistant },
   { label: 'Show Floating Agent', click: showAgent },
   { label: 'Open Dashboard', click: openDashboard },
   { label: 'Settings', click: () => { showAssistant(); mainWin?.webContents.send('open-settings') } },
   { type: 'separator' },
   { label: 'Quit', click: () => app.quit() },
 ]))
 tray.on('click', showAssistant)
}

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

  const windowWidth = Math.min(1420, Math.floor(screenWidth * 0.95))
  const windowHeight = Math.min(890, Math.floor(screenHeight * 0.94))

  const win = new BrowserWindow({
    show: false, // the floating agent is the primary surface; open this from the tray or agent menu
    width: windowWidth,
    height: windowHeight,
    minWidth: 1080,
    minHeight: 700,
    center: true,
    frame: false,
    transparent: true,
    alwaysOnTop: false,
    skipTaskbar: false,
    resizable: true,
    backgroundColor: '#050711',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWin = win
  win.on('closed', () => { if (mainWin === win) mainWin = null })
  win.loadFile(path.join(__dirname, 'index.html'))
  const signalTimer = setInterval(() => {
    if (win.isDestroyed()) return
    const point = screen.getCursorScreenPoint()
    win.webContents.send('companion-signal', {
      cursor: { x: point.x, y: point.y },
      windowBounds: win.getBounds(),
      idleSeconds: powerMonitor.getSystemIdleTime(),
      observedAt: new Date().toISOString(),
    })
  }, 120)
  win.on('closed', () => clearInterval(signalTimer))
}

ipcMain.handle('window-minimize', () => {
  const win = mainWin
  if (win) win.minimize()
  return true
})

ipcMain.handle('window-maximize', () => {
  const win = mainWin
  if (win) {
    if (win.isMaximized()) win.unmaximize()
    else win.maximize()
  }
  return true
})

ipcMain.handle('window-close', () => {
  const win = mainWin
  if (win) win.hide()
  return true
})

function getLocalApiToken() {
  if (process.env.ASSISTANT_API_TOKEN) return process.env.ASSISTANT_API_TOKEN;
  try {
    const fs = require('fs');
    const localAppData = process.env.LOCALAPPDATA || path.join(process.env.USERPROFILE || '', 'AppData', 'Local');
    const tokenFile = path.join(localAppData, 'LivingAssistant', 'LivingAssistant', 'api_token');
    if (fs.existsSync(tokenFile)) {
      return fs.readFileSync(tokenFile, 'utf8').trim();
    }
  } catch (_) {}
  return '';
}

ipcMain.handle('assistant-config', () => ({
  baseUrl: process.env.ASSISTANT_API_URL || 'http://127.0.0.1:8787',
  token: getLocalApiToken(),
  platform: process.platform,
}))

ipcMain.handle('companion-show', () => {
  showAssistant()
  return Boolean(mainWin)
})

ipcMain.handle('companion-ignore-mouse', (_event, ignore) => {
  const win = mainWin
  if (!win) return false
  win.setIgnoreMouseEvents(Boolean(ignore), { forward: true })
  return true
})

ipcMain.handle('companion-size', (_event, expanded) => {
  const win = mainWin
  if (!win) return false
  if (expanded) {
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize
    const w = Math.min(1380, Math.floor(screenWidth * 0.94))
    const h = Math.min(880, Math.floor(screenHeight * 0.94))
    win.setMinimumSize(1024, 680)
    win.setResizable(true)
    win.setSize(w, h, true)
    win.center()
    win.setAlwaysOnTop(false)
    win.setIgnoreMouseEvents(false)
  } else {
    win.setMinimumSize(100, 100)
    win.setSize(100, 100, true)
    win.setResizable(false)
    win.setAlwaysOnTop(true)
  }
  return true
})

ipcMain.handle('companion-move', (_event, deltaX, deltaY) => {
  const win = mainWin
  if (!win) return false
  const [x, y] = win.getPosition()
  win.setPosition(Math.round(x + deltaX), Math.round(y + deltaY), false)
  return true
})

ipcMain.handle('read-local-media', async (_event, targetPath) => {
  try {
    const fs = require('fs');
    const path = require('path');
    if (!targetPath || typeof targetPath !== 'string') return null;
    const cleanPath = targetPath.replace(/^file:\/\/\/?/, '').replace(/\//g, path.sep);
    if (!fs.existsSync(cleanPath)) return null;
    const stat = fs.statSync(cleanPath);
    if (!stat.isFile() || stat.size > 25 * 1024 * 1024) return null; // 25MB max
    const ext = path.extname(cleanPath).toLowerCase();
    const mimeMap = {
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.webp': 'image/webp',
      '.gif': 'image/gif',
      '.svg': 'image/svg+xml',
    };
    const mime = mimeMap[ext] || 'image/jpeg';
    const data = fs.readFileSync(cleanPath);
    return `data:${mime};base64,${data.toString('base64')}`;
  } catch (_) {
    return null;
  }
})

app.whenReady().then(() => {
  createWindow()
  createAgentWindow()
  createTray()
  globalShortcut.register('CommandOrControl+Shift+Space', () => {
    const win = mainWin
    if (!win) return
    if (win.isVisible()) win.hide()
    else {
      win.show()
      win.focus()
    }
  })
  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', function () {
  globalShortcut.unregisterAll()
  if (process.platform !== 'darwin') app.quit()
})

ipcMain.on('companion-hide', () => {
  hideAssistant()
})
