import { Minus, Square, X, Search } from 'lucide-react'
import ConnectionStatus from './ConnectionStatus'
import { useAppStore } from '../store'

export default function TitleBar() {
  const { setCommandPaletteOpen } = useAppStore()

  const handleMinimize = () => window.electronAPI?.window.minimize()
  const handleMaximize = () => window.electronAPI?.window.maximize()
  const handleClose = () => window.electronAPI?.window.close()

  return (
    <div
      className="drag-region flex items-center justify-between h-10 px-4 border-b border-border select-none"
      style={{ background: 'var(--sidebar-bg)' }}
    >
      {/* Left: Logo */}
      <div className="flex items-center gap-3 no-drag">
        <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-sm">
          <span className="text-white text-[10px] font-bold">A</span>
        </div>
        <span className="text-sm font-semibold text-text-primary">Agent Desktop</span>
      </div>

      {/* Center: Command palette trigger + Connection */}
      <div className="flex items-center gap-3 no-drag">
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="flex items-center gap-2 px-3 py-1 text-xs text-text-tertiary rounded-lg border border-border hover:bg-surface-tertiary hover:text-text-secondary transition-colors"
        >
          <Search size={12} />
          <span>搜索命令</span>
          <kbd className="text-[10px] bg-surface-tertiary px-1 py-0.5 rounded border border-border">⌘K</kbd>
        </button>
        <ConnectionStatus />
      </div>

      {/* Right: Window controls (Windows) */}
      <div className="flex items-center gap-0 no-drag">
        <button
          onClick={handleMinimize}
          className="w-10 h-8 flex items-center justify-center hover:bg-surface-tertiary transition-colors rounded"
        >
          <Minus size={14} className="text-text-secondary" />
        </button>
        <button
          onClick={handleMaximize}
          className="w-10 h-8 flex items-center justify-center hover:bg-surface-tertiary transition-colors rounded"
        >
          <Square size={12} className="text-text-secondary" />
        </button>
        <button
          onClick={handleClose}
          className="w-10 h-8 flex items-center justify-center hover:bg-red-500 hover:text-white transition-colors rounded group"
        >
          <X size={14} className="text-text-secondary group-hover:text-white" />
        </button>
      </div>
    </div>
  )
}
