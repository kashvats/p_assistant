const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('assistantDesktop', {
  getConfig: () => ipcRenderer.invoke('assistant-config'),
  onSignal: (callback) => ipcRenderer.on('companion-signal', (_event, signal) => callback(signal)),
  hide: () => ipcRenderer.send('companion-hide'),
  show: () => ipcRenderer.invoke('companion-show'),
  setExpanded: (expanded) => ipcRenderer.invoke('companion-size', Boolean(expanded)),
  moveWindow: (deltaX, deltaY) => ipcRenderer.invoke('companion-move', Number(deltaX), Number(deltaY)),
})
