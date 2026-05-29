export interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileTreeNode[]
}

export interface ElectronAPI {
  agent: {
    start: (port?: number) => Promise<{ success: boolean; port: number; error?: string }>
    stop: () => Promise<{ success: boolean }>
    status: () => Promise<{ running: boolean }>
    onLog: (callback: (log: string) => void) => void
    onError: (callback: (error: string) => void) => void
    onStatusChange: (callback: (status: 'starting' | 'running' | 'stopped' | 'error') => void) => void
  }
  secrets: {
    save: (secrets: Record<string, string>) => Promise<{ success: boolean; error?: string }>
    load: () => Promise<{ success: boolean; secrets: Record<string, string>; error?: string }>
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
  project: {
    openFolder: () => Promise<{ path: string } | null>
    readDir: (dirPath: string) => Promise<FileTreeNode[]>
    readFile: (filePath: string) => Promise<{ success: boolean; content?: string; error?: string }>
  }
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}
