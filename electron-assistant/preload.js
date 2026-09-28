const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('assistantDesktop', {
  getConfig: () => ipcRenderer.invoke('assistant-config'),
  onSignal: (callback) => ipcRenderer.on('companion-signal', (_event, signal) => callback(signal)),
  onOpenSettings: (callback) => ipcRenderer.on('open-settings', () => callback()),
  hide: () => ipcRenderer.send('companion-hide'),
  show: () => ipcRenderer.invoke('companion-show'),
  minimize: () => ipcRenderer.invoke('window-minimize'),
  maximize: () => ipcRenderer.invoke('window-maximize'),
  close: () => ipcRenderer.invoke('window-close'),
  setExpanded: (expanded) => ipcRenderer.invoke('companion-size', Boolean(expanded)),
  setIgnoreMouse: (ignore) => ipcRenderer.invoke('companion-ignore-mouse', Boolean(ignore)),
  moveWindow: (deltaX, deltaY) => ipcRenderer.invoke('companion-move', Number(deltaX), Number(deltaY)),
  readLocalMedia: (filePath) => ipcRenderer.invoke('read-local-media', filePath),
})

