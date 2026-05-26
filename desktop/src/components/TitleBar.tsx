import { Minus, Square, X } from 'lucide-react'

export default function TitleBar() {
  const handleMinimize = () => window.electronAPI?.window.minimize()
  const handleMaximize = () => window.electronAPI?.window.maximize()
  const handleClose = () => window.electronAPI?.window.close()

  return (
    <div className="drag-region flex items-center justify-between h-10 px-4 bg-sidebar-bg border-b border-gray-200 select-none">
      {/* 左侧：Logo + 导航按钮 */}
      <div className="flex items-center gap-2 no-drag">
        <div className="w-6 h-6 rounded-full bg-primary-500 flex items-center justify-center">
          <span className="text-white text-xs font-bold">A</span>
        </div>
        <span className="text-sm font-semibold text-gray-700">Agent Desktop</span>
      </div>

      {/* 右侧：窗口控制按钮 (Windows) */}
      <div className="flex items-center gap-0 no-drag">
        <button
          onClick={handleMinimize}
          className="w-10 h-8 flex items-center justify-center hover:bg-gray-200 transition-colors"
        >
          <Minus size={14} className="text-gray-600" />
        </button>
        <button
          onClick={handleMaximize}
          className="w-10 h-8 flex items-center justify-center hover:bg-gray-200 transition-colors"
        >
          <Square size={12} className="text-gray-600" />
        </button>
        <button
          onClick={handleClose}
          className="w-10 h-8 flex items-center justify-center hover:bg-red-500 hover:text-white transition-colors"
        >
          <X size={14} className="text-gray-600 hover:text-white" />
        </button>
      </div>
    </div>
  )
}
