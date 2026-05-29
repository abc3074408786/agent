import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, MessageSquare, Settings, Users, Bot, Zap,
  Plus, Clock, Command
} from 'lucide-react'
import { useAppStore, AVAILABLE_AGENTS } from '../store'

interface CommandItem {
  id: string
  icon: React.ReactNode
  label: string
  description?: string
  shortcut?: string
  action: () => void
  category: 'navigation' | 'action' | 'agent' | 'session'
}

export default function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen, sessions, createSession } = useAppStore()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Global keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandPaletteOpen(!commandPaletteOpen)
      }
      if (e.key === 'Escape' && commandPaletteOpen) {
        setCommandPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [commandPaletteOpen, setCommandPaletteOpen])

  // Focus input when opened
  useEffect(() => {
    if (commandPaletteOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [commandPaletteOpen])

  // Build command list
  const commands: CommandItem[] = [
    // Navigation
    {
      id: 'nav-home', icon: <MessageSquare size={16} />, label: '首页',
      description: '返回欢迎页', shortcut: '',
      action: () => { navigate('/'); close() }, category: 'navigation'
    },
    {
      id: 'nav-settings', icon: <Settings size={16} />, label: '设置',
      description: '打开设置页面', shortcut: '⌘,',
      action: () => { navigate('/settings'); close() }, category: 'navigation'
    },
    {
      id: 'nav-agents', icon: <Bot size={16} />, label: '多 Agent 并行',
      description: '打开多 Agent 任务面板',
      action: () => { navigate('/agents'); close() }, category: 'navigation'
    },
    {
      id: 'nav-team', icon: <Users size={16} />, label: '团队开发',
      description: 'Leader + Worker 协作',
      action: () => { navigate('/team'); close() }, category: 'navigation'
    },
    {
      id: 'nav-auto', icon: <Clock size={16} />, label: '定时任务',
      description: '自动化任务管理',
      action: () => { navigate('/automations'); close() }, category: 'navigation'
    },
    // Actions
    {
      id: 'action-new-session', icon: <Plus size={16} />, label: '新建对话',
      description: '创建一个新的聊天会话', shortcut: '⌘N',
      action: () => { const id = createSession(); navigate(`/chat/${id}`); close() }, category: 'action'
    },
    // Agents
    ...AVAILABLE_AGENTS.map((agent) => ({
      id: `agent-${agent.id}`,
      icon: <span className="text-base">{agent.icon}</span>,
      label: agent.name,
      description: agent.description,
      action: () => { const id = createSession(agent.id); navigate(`/chat/${id}`); close() },
      category: 'agent' as const,
    })),
    // Recent sessions
    ...sessions.slice(0, 5).map((session) => ({
      id: `session-${session.id}`,
      icon: <MessageSquare size={16} />,
      label: session.title,
      description: `${session.messages.length} 条消息`,
      action: () => { navigate(`/chat/${session.id}`); close() },
      category: 'session' as const,
    })),
  ]

  const close = () => setCommandPaletteOpen(false)

  // Filter
  const filtered = query.trim()
    ? commands.filter(
        (c) =>
          c.label.toLowerCase().includes(query.toLowerCase()) ||
          c.description?.toLowerCase().includes(query.toLowerCase())
      )
    : commands

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action()
      }
    }
  }

  if (!commandPaletteOpen) return null

  // Group filtered results
  const groups = new Map<string, CommandItem[]>()
  filtered.forEach((item) => {
    const group = groups.get(item.category) || []
    group.push(item)
    groups.set(item.category, group)
  })

  const categoryLabels: Record<string, string> = {
    navigation: '导航',
    action: '操作',
    agent: '使用 Agent',
    session: '最近对话',
  }

  let flatIndex = -1

  return (
    <div
      className="fixed inset-0 z-[9998] flex items-start justify-center pt-[15vh]"
      onClick={close}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 animate-fade-in" />

      {/* Panel */}
      <div
        className="relative w-[560px] max-h-[420px] rounded-2xl border border-border overflow-hidden shadow-2xl animate-scale-in"
        style={{ background: 'var(--surface-primary)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <Search size={18} className="text-text-tertiary shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }}
            onKeyDown={handleKeyDown}
            placeholder="搜索命令、Agent、对话..."
            className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder-text-tertiary"
          />
          <kbd className="hidden sm:flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] text-text-tertiary bg-surface-tertiary rounded border border-border">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="overflow-y-auto max-h-[340px] py-2">
          {filtered.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-text-tertiary">无匹配结果</p>
          )}

          {Array.from(groups.entries()).map(([category, items]) => (
            <div key={category}>
              <p className="px-4 pt-2 pb-1 text-[10px] font-semibold text-text-tertiary uppercase tracking-wider">
                {categoryLabels[category] || category}
              </p>
              {items.map((item) => {
                flatIndex++
                const idx = flatIndex
                return (
                  <button
                    key={item.id}
                    onClick={item.action}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                      idx === selectedIndex
                        ? 'bg-primary-500/10 text-primary-500'
                        : 'text-text-primary hover:bg-surface-tertiary'
                    }`}
                  >
                    <span className="text-text-secondary shrink-0">{item.icon}</span>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm">{item.label}</span>
                      {item.description && (
                        <span className="ml-2 text-xs text-text-tertiary">{item.description}</span>
                      )}
                    </div>
                    {item.shortcut && (
                      <kbd className="text-[10px] text-text-tertiary bg-surface-tertiary px-1.5 py-0.5 rounded border border-border">
                        {item.shortcut}
                      </kbd>
                    )}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
