import { useState, useRef, KeyboardEvent } from 'react'
import { Send, Plus, ChevronDown } from 'lucide-react'
import { useAppStore } from '../store'

interface InputBoxProps {
  onSend: (message: string) => void
  placeholder?: string
  disabled?: boolean
}

export default function InputBox({ onSend, placeholder, disabled }: InputBoxProps) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { settings } = useAppStore()

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    // 重置高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
    }
  }

  return (
    <div className="relative border border-gray-200 rounded-xl bg-white shadow-sm hover:shadow-md transition-shadow">
      {/* 文本输入区 */}
      <div className="px-4 pt-3 pb-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={placeholder || '输入消息...'}
          disabled={disabled}
          rows={1}
          className="w-full resize-none outline-none text-sm text-gray-700 placeholder-gray-400 bg-transparent leading-6 max-h-[200px]"
        />
      </div>

      {/* 底部工具栏 */}
      <div className="flex items-center justify-between px-3 pb-2">
        {/* 左侧：附件按钮 */}
        <div className="flex items-center gap-1">
          <button className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
            <Plus size={18} />
          </button>
        </div>

        {/* 右侧：模型选择 + 发送 */}
        <div className="flex items-center gap-2">
          {/* 模型选择器 */}
          <button className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 rounded-lg hover:bg-gray-100 transition-colors">
            <span className="w-3 h-3 rounded-full bg-green-400" />
            <span>{settings.defaultModel}</span>
            <ChevronDown size={12} />
          </button>

          {/* 发送按钮 */}
          <button
            onClick={handleSend}
            disabled={!text.trim() || disabled}
            className={`p-2 rounded-lg transition-colors ${
              text.trim() && !disabled
                ? 'bg-primary-500 text-white hover:bg-primary-600'
                : 'bg-gray-100 text-gray-300'
            }`}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
