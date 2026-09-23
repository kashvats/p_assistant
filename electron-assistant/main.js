const { app, BrowserWindow, ipcMain, screen, powerMonitor, globalShortcut } = require('electron')
const path = require('path')

function createWindow() {
  const win = new BrowserWindow({
    width: 112,
    height: 112,
    x: 50,
    y: 50,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: true,
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

ipcMain.handle('assistant-config', () => ({
  baseUrl: process.env.ASSISTANT_API_URL || 'http://127.0.0.1:8787',
  token: process.env.ASSISTANT_API_TOKEN || '',
  platform: process.platform,
}))

ipcMain.handle('companion-show', () => {
  const win = BrowserWindow.getAllWindows()[0]
  if (win) win.show()
  return Boolean(win)
})

ipcMain.handle('companion-size', (_event, expanded) => {
  const win = BrowserWindow.getAllWindows()[0]
  if (!win) return false
  win.setSize(expanded ? 410 : 112, expanded ? 650 : 112, true)
  return true
})

app.whenReady().then(() => {
  createWindow()
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
  const win = BrowserWindow.getAllWindows()[0]
  if (win) win.hide()
})
