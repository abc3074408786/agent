export interface ElectronAPI {
  agent: {
    start: (port?: number) => Promise<{ success: boolean; port: number }>
    stop: () => Promise<{ success: boolean }>
    status: () => Promise<{ running: boolean }>
    onLog: (callback: (log: string) => void) => void
    onError: (callback: (error: string) => void) => void
    onStatus: (callback: (status: string) => void) => void
  }
  window: {
    minimize: () => Promise<void>
    maximize: () => Promise<void>
    close: () => Promise<void>
    isMaximized: () => Promise<boolean>
  }
  app: {
    getDataPath: () => Promise<string>
  }
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}
