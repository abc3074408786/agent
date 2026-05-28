/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface ElectronAPI {
  getServerInfo: () => Promise<{ port: number; isRunning: boolean; agentRoot: string }>
  startPythonServer: () => Promise<{ status: string }>
  stopPythonServer: () => Promise<{ status: string }>
  getAppInfo: () => Promise<{
    version: string
    platform: string
    isDev: boolean
    electronVersion: string
    nodeVersion: string
  }>
  onPythonStatus: (callback: (data: any) => void) => () => void
  onPythonLog: (callback: (data: any) => void) => () => void
}

interface Window {
  electronAPI: ElectronAPI
}
