// Minimal bridge for the floating agent page: window movement and size, click-through,
// the native context menu, opening the dashboard, the global cursor position, a
// user-initiated screen capture and quitting after the kill switch. Nothing else is exposed.
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('agentShell', {
  moveBy: (dx, dy) => ipcRenderer.invoke('agent-move', Number(dx) || 0, Number(dy) || 0),
  dragStart: () => ipcRenderer.invoke('agent-drag-start'),
  dragMove: () => ipcRenderer.invoke('agent-drag-move'),
  dragEnd: () => ipcRenderer.invoke('agent-drag-end'),
  savePosition:() => ipcRenderer.invoke('agent-save-position'),
  setClickThrough: (on) => ipcRenderer.invoke('agent-click-through', Boolean(on)),
  setExpanded: (on) => ipcRenderer.invoke('agent-expand', Boolean(on)),
  openDashboard: () => ipcRenderer.invoke('agent-open-dashboard'),
  captureScreen: () => ipcRenderer.invoke('agent-capture-screen'),  // PNG data URL of the display under the agent
  quitApp: () => ipcRenderer.invoke('agent-quit'),  // after the kill switch shut the backend down
  menu: (opts) => ipcRenderer.invoke('agent-menu', { speakReplies: Boolean(opts && opts.speakReplies) }),
  onCursor: (cb) => ipcRenderer.on('agent-cursor', (_e, point) => cb(point)),
  onMenuAction: (cb) => ipcRenderer.on('agent-menu-action', (_e, action) => cb(action)),
})
