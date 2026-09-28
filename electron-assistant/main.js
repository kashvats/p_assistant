const { app, BrowserWindow, ipcMain, screen, powerMonitor, globalShortcut, Tray, Menu, nativeImage } = require('electron')
const path = require('path')

let tray = null

function showAssistant() {
 const win = BrowserWindow.getAllWindows()[0]
 if (win) { win.show(); win.focus() }
}

function hideAssistant() {
 const win = BrowserWindow.getAllWindows()[0]
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
   { label: 'Open Aura OS', click: () => { const { shell } = require('electron'); shell.openExternal(process.env.ASSISTANT_API_URL ? `${process.env.ASSISTANT_API_URL}/aura` : 'http://127.0.0.1:8787/aura') } },
   { label: 'Settings', click: () => { showAssistant(); BrowserWindow.getAllWindows()[0]?.webContents.send('open-settings') } },
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
  const win = BrowserWindow.getAllWindows()[0]
  if (win) win.minimize()
  return true
})

ipcMain.handle('window-maximize', () => {
  const win = BrowserWindow.getAllWindows()[0]
  if (win) {
    if (win.isMaximized()) win.unmaximize()
    else win.maximize()
  }
  return true
})

ipcMain.handle('window-close', () => {
  const win = BrowserWindow.getAllWindows()[0]
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
  return Boolean(BrowserWindow.getAllWindows()[0])
})

ipcMain.handle('companion-ignore-mouse', (_event, ignore) => {
  const win = BrowserWindow.getAllWindows()[0]
  if (!win) return false
  win.setIgnoreMouseEvents(Boolean(ignore), { forward: true })
  return true
})

ipcMain.handle('companion-size', (_event, expanded) => {
  const win = BrowserWindow.getAllWindows()[0]
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
  const win = BrowserWindow.getAllWindows()[0]
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
  createTray()
  globalShortcut.register('CommandOrControl+Shift+Space', () => {
    const win = BrowserWindow.getAllWindows()[0]
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
