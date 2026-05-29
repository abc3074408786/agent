import { ReactNode, useEffect } from 'react'
import Sidebar from './Sidebar'
import TitleBar from './TitleBar'
import ArtifactsPanel from './ArtifactsPanel'
import { useAppStore } from '../store'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { settings, fetchRemoteConfig } = useAppStore()

  // Apply theme class to document
  useEffect(() => {
    const root = document.documentElement
    if (settings.theme === 'dark') {
      root.classList.add('dark')
    } else if (settings.theme === 'light') {
      root.classList.remove('dark')
    } else {
      // system
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      if (prefersDark) {
        root.classList.add('dark')
      } else {
        root.classList.remove('dark')
      }
    }
  }, [settings.theme])

  // Fetch remote models/agents on mount and when connection settings change
  useEffect(() => {
    fetchRemoteConfig()
  }, [settings.agentMode, settings.agentLocalPort, settings.agentRemoteUrl])

  return (
    <div className="flex flex-col h-screen w-screen transition-theme" style={{ background: 'var(--surface-primary)' }}>
      {/* Title bar */}
      <TitleBar />

      {/* Main body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar />

        {/* Main content */}
        <main className="flex-1 overflow-hidden" style={{ background: 'var(--surface-primary)' }}>
          {children}
        </main>

        {/* Artifacts panel */}
        <ArtifactsPanel />
      </div>
    </div>
  )
}
