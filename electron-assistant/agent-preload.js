// Minimal bridge for the floating agent page: window movement, click-through,
// the native context menu and the global cursor position. Nothing else is exposed.
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('agentShell', {
  moveBy: (dx, dy) => ipcRenderer.invoke('agent-move', Number(dx) || 0, Number(dy) || 0),
  setClickThrough: (on) => ipcRenderer.invoke('agent-click-through', Boolean(on)),
  menu: (opts) => ipcRenderer.invoke('agent-menu', { speakReplies: Boolean(opts && opts.speakReplies) }),
  onCursor: (cb) => ipcRenderer.on('agent-cursor', (_e, point) => cb(point)),
  onMenuAction: (cb) => ipcRenderer.on('agent-menu-action', (_e, action) => cb(action)),
})
