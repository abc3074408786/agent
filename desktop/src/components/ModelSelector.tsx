import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { useAppStore, AVAILABLE_MODELS, AVAILABLE_AGENTS, ModelOption, AgentOption } from '../store'

interface ModelSelectorProps {
  compact?: boolean
}

export function ModelSelector({ compact = false }: ModelSelectorProps) {
  const { settings, updateSettings } = useAppStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const currentModel = AVAILABLE_MODELS.find((m) => m.id === settings.defaultModel) || AVAILABLE_MODELS[0]

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectModel = (model: ModelOption) => {
    updateSettings({ defaultModel: model.id })
    setOpen(false)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border transition-all
          border-border text-text-secondary hover:text-text-primary hover:border-text-tertiary
          bg-surface-primary"
      >
        <span
          className="w-2 h-2 rounded-full"
          style={{ background: currentModel.provider === 'openai' ? '#10b981' : '#a78bfa' }}
        />
        {!compact && <span className="max-w-[100px] truncate">{currentModel.name}</span>}
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          className="absolute bottom-full mb-2 left-0 w-56 rounded-xl border border-border overflow-hidden animate-scale-in z-50"
          style={{ background: 'var(--dropdown-bg)', boxShadow: 'var(--dropdown-shadow)' }}
        >
          <div className="px-3 py-2 border-b border-border">
            <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider">选择模型</p>
          </div>
          <div className="py-1 max-h-[250px] overflow-y-auto">
            {/* OpenAI */}
            <p className="px-3 pt-2 pb-1 text-[10px] text-text-tertiary">OpenAI</p>
            {AVAILABLE_MODELS.filter((m) => m.provider === 'openai').map((model) => (
              <ModelItem
                key={model.id}
                model={model}
                selected={model.id === settings.defaultModel}
                onSelect={selectModel}
              />
            ))}
            {/* Anthropic */}
            <p className="px-3 pt-3 pb-1 text-[10px] text-text-tertiary">Anthropic</p>
            {AVAILABLE_MODELS.filter((m) => m.provider === 'anthropic').map((model) => (
              <ModelItem
                key={model.id}
                model={model}
                selected={model.id === settings.defaultModel}
                onSelect={selectModel}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ModelItem({
  model, selected, onSelect
}: { model: ModelOption; selected: boolean; onSelect: (m: ModelOption) => void }) {
  return (
    <button
      onClick={() => onSelect(model)}
      className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
        selected ? 'bg-primary-500/10 text-primary-500' : 'text-text-primary hover:bg-surface-tertiary'
      }`}
    >
      <span className="text-xs opacity-60">{model.icon}</span>
      <span className="flex-1 text-left text-xs">{model.name}</span>
      {selected && <Check size={14} className="text-primary-500" />}
    </button>
  )
}

// Agent Selector
interface AgentSelectorProps {
  value?: string
  onChange?: (agentId: string) => void
  compact?: boolean
}

export function AgentSelector({ value, onChange, compact = false }: AgentSelectorProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const currentAgent = AVAILABLE_AGENTS.find((a) => a.id === (value || 'default')) || AVAILABLE_AGENTS[0]

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border transition-all
          border-border text-text-secondary hover:text-text-primary hover:border-text-tertiary
          bg-surface-primary"
      >
        <span>{currentAgent.icon}</span>
        {!compact && <span className="max-w-[80px] truncate">{currentAgent.name}</span>}
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          className="absolute bottom-full mb-2 right-0 w-64 rounded-xl border border-border overflow-hidden animate-scale-in z-50"
          style={{ background: 'var(--dropdown-bg)', boxShadow: 'var(--dropdown-shadow)' }}
        >
          <div className="px-3 py-2 border-b border-border">
            <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider">选择 Agent</p>
          </div>
          <div className="py-1 max-h-[300px] overflow-y-auto">
            {AVAILABLE_AGENTS.map((agent) => (
              <button
                key={agent.id}
                onClick={() => { onChange?.(agent.id); setOpen(false) }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 transition-colors ${
                  agent.id === (value || 'default')
                    ? 'bg-primary-500/10 text-primary-500'
                    : 'text-text-primary hover:bg-surface-tertiary'
                }`}
              >
                <span className="text-lg">{agent.icon}</span>
                <div className="flex-1 text-left">
                  <p className="text-xs font-medium">{agent.name}</p>
                  <p className="text-[10px] text-text-tertiary">{agent.description}</p>
                </div>
                {agent.id === (value || 'default') && <Check size={14} className="text-primary-500" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
