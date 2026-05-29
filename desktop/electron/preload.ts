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
    onStatusChange: (callback: (status: string) => void) => {
      ipcRenderer.on('agent:status-change', (_event, status) => callback(status))
    }
  },

  // 加密存储（API Key 等敏感信息）
  secrets: {
    save: (secrets: Record<string, string>) => ipcRenderer.invoke('secrets:save', secrets),
    load: () => ipcRenderer.invoke('secrets:load')
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
  },

  // 项目文件系统
  project: {
    openFolder: () => ipcRenderer.invoke('project:openFolder'),
    readDir: (dirPath: string) => ipcRenderer.invoke('project:readDir', dirPath),
    readFile: (filePath: string) => ipcRenderer.invoke('project:readFile', filePath)
  },

  // VSCode 集成
  vscode: {
    openFile: (filePath: string, line?: number) => ipcRenderer.invoke('vscode:openFile', filePath, line),
    openFolder: (folderPath: string) => ipcRenderer.invoke('vscode:openFolder', folderPath)
  },

  // Codex CLI (ACP 协议桥接)
  codex: {
    start: (cwd?: string) => ipcRenderer.invoke('codex:start', cwd),
    stop: () => ipcRenderer.invoke('codex:stop'),
    createSession: (cwd: string) => ipcRenderer.invoke('codex:createSession', cwd),
    sendMessage: (sessionId: string, content: string) => ipcRenderer.invoke('codex:sendMessage', sessionId, content),
    sendRaw: (message: object) => ipcRenderer.invoke('codex:sendRaw', message),
    status: () => ipcRenderer.invoke('codex:status'),
    onMessage: (callback: (msg: any) => void) => {
      ipcRenderer.on('codex:message', (_event, msg) => callback(msg))
    },
    onLog: (callback: (log: string) => void) => {
      ipcRenderer.on('codex:log', (_event, log) => callback(log))
    },
    onDisconnected: (callback: (info: { code: number }) => void) => {
      ipcRenderer.on('codex:disconnected', (_event, info) => callback(info))
    },
    onError: (callback: (error: string) => void) => {
      ipcRenderer.on('codex:error', (_event, error) => callback(error))
    }
  }
})
