const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('assistantDesktop', {
  getConfig: () => ipcRenderer.invoke('assistant-config'),
})
