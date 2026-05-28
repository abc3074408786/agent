import { contextBridge, ipcRenderer } from 'electron'

// 暴露安全的 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // Python 后端控制
  getServerInfo: () => ipcRenderer.invoke('get-server-info'),
  startPythonServer: () => ipcRenderer.invoke('start-python-server'),
  stopPythonServer: () => ipcRenderer.invoke('stop-python-server'),

  // 应用信息
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),

  // 监听主进程事件
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
