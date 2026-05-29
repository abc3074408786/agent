import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store'
import { Send, Plus, ChevronDown, Command } from 'lucide-react'
import { ModelSelector, AgentSelector } from '../components/ModelSelector'

export default function WelcomePage() {
  const navigate = useNavigate()
  const { createSession, setPendingSessionId, setCommandPaletteOpen, getAgents } = useAppStore()
  const [activeAgent, setActiveAgent] = useState('default')
  const [inputText, setInputText] = useState('')

  const agents = getAgents()

  const handleSelectAgent = (agentId: string) => {
    const sessionId = createSession(agentId !== 'default' ? agentId : undefined)
    navigate(`/chat/${sessionId}`)
  }

  const handleSendMessage = () => {
    if (!inputText.trim()) return
    const sessionId = createSession(activeAgent !== 'default' ? activeAgent : undefined)
    useAppStore.getState().addMessage(sessionId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: inputText.trim(),
      timestamp: Date.now()
    })
    setPendingSessionId(sessionId)
    navigate(`/chat/${sessionId}`)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto" style={{ background: 'var(--surface-primary)' }}>
      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 pb-4">
        {/* Greeting */}
        <h1 className="text-3xl font-bold text-text-primary mb-2">Hi，有什么可以帮你？</h1>
        <p className="text-sm text-text-tertiary mb-8">选择一个 Agent 或直接输入你的需求</p>

        {/* Input box */}
        <div className="w-full max-w-2xl mb-8">
          <div
            className="relative rounded-xl border border-border shadow-sm"
            style={{ background: 'var(--input-bg)' }}
          >
            <div className="px-4 pt-3 pb-2">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="描述你想做的事情..."
                rows={2}
                className="w-full resize-none outline-none text-sm bg-transparent leading-6 text-text-primary placeholder-text-tertiary"
              />
            </div>

            <div className="flex items-center justify-between px-3 pb-2.5">
              <div className="flex items-center gap-1">
                <button className="p-1.5 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors">
                  <Plus size={16} />
                </button>
              </div>

              <div className="flex items-center gap-2">
                <ModelSelector />
                <AgentSelector value={activeAgent} onChange={setActiveAgent} />

                <button
                  onClick={handleSendMessage}
                  disabled={!inputText.trim()}
                  className={`p-2 rounded-lg transition-colors ${
                    inputText.trim()
                      ? 'bg-primary-500 text-white hover:bg-primary-600'
                      : 'text-text-tertiary'
                  }`}
                  style={!inputText.trim() ? { background: 'var(--surface-tertiary)' } : undefined}
                >
                  <Send size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Shortcut hint */}
          <div className="mt-2 flex items-center justify-center gap-4">
            <button
              onClick={() => setCommandPaletteOpen(true)}
              className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
            >
              <Command size={11} />
              <span>⌘K 快捷命令</span>
            </button>
          </div>
        </div>

        {/* Agent grid */}
        <div className="w-full max-w-4xl">
          <p className="text-center text-xs text-text-tertiary mb-4 uppercase tracking-wider font-semibold">
            选择专业 Agent
          </p>
          <div className="grid grid-cols-4 gap-3">
            {agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => handleSelectAgent(agent.id)}
                className="flex flex-col items-center gap-2 p-4 rounded-xl border border-border transition-all group hover:border-primary-300 hover:shadow-md"
                style={{ background: 'var(--surface-secondary)' }}
              >
                <span className="text-2xl group-hover:scale-110 transition-transform">{agent.icon}</span>
                <span className="text-xs font-medium text-text-primary group-hover:text-primary-500 transition-colors">
                  {agent.name}
                </span>
                <span className="text-[10px] text-text-tertiary text-center line-clamp-1">
                  {agent.description}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
