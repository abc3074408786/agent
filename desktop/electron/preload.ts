import { contextBridge, ipcRenderer } from 'electron'

// 暴露安全的 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // Agent 进程管理
  agent: {
    start: (port?: number) => ipcRenderer.invoke('agent:start', port),
    stop: () => ipcRenderer.invoke('agent:stop'),
    status: () => ipcRenderer.invoke('agent:status'),
    onLog: (callback: (log: string) => void) => {
      ipcRenderer.on('agent:log', (_event, log) => callback(log))
    },
    onError: (callback: (error: string) => void) => {
      ipcRenderer.on('agent:error', (_event, error) => callback(error))
    },
    onStatus: (callback: (status: string) => void) => {
      ipcRenderer.on('agent:status', (_event, status) => callback(status))
    }
  },

  // 窗口控制
  window: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized')
  },

  // 应用信息
  app: {
    getDataPath: () => ipcRenderer.invoke('app:getDataPath')
  }
})
