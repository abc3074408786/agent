import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getServerInfo: () => ipcRenderer.invoke('get-server-info'),
  startPythonServer: () => ipcRenderer.invoke('start-python-server'),
  stopPythonServer: () => ipcRenderer.invoke('stop-python-server'),
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),

  onPythonStatus: (callback: (data: any) => void) => {
    const listener = (_event: any, data: any) => callback(data)
    ipcRenderer.on('python-status', listener)
    return () => ipcRenderer.removeListener('python-status', listener)
  },

  onPythonLog: (callback: (data: any) => void) => {
    const listener = (_event: any, data: any) => callback(data)
    ipcRenderer.on('python-log', listener)
    return () => ipcRenderer.removeListener('python-log', listener)
  },
})
