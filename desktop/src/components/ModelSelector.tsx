import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { useAppStore, AVAILABLE_MODELS, AVAILABLE_AGENTS, ModelOption, AgentOption } from '../store'

interface ModelSelectorProps {
  compact?: boolean
}

export function ModelSelector({ compact = false }: ModelSelectorProps) {
  const { settings, updateSettings, getModels } = useAppStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const models = getModels()
  const currentModel = models.find((m) => m.id === settings.defaultModel) || models[0]

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
            {models.filter((m) => m.provider === 'openai').map((model) => (
              <ModelItem
                key={model.id}
                model={model}
                selected={model.id === settings.defaultModel}
                onSelect={selectModel}
              />
            ))}
            {/* Anthropic */}
            <p className="px-3 pt-3 pb-1 text-[10px] text-text-tertiary">Anthropic</p>
            {models.filter((m) => m.provider === 'anthropic').map((model) => (
              <ModelItem
                key={model.id}
                model={model}
                selected={model.id === settings.defaultModel}
                onSelect={selectModel}
              />
            ))}
            {/* Custom */}
            {models.filter((m) => m.provider === 'custom').length > 0 && (
              <>
                <p className="px-3 pt-3 pb-1 text-[10px] text-text-tertiary">自定义</p>
                {models.filter((m) => m.provider === 'custom').map((model) => (
                  <ModelItem
                    key={model.id}
                    model={model}
                    selected={model.id === settings.defaultModel}
                    onSelect={selectModel}
                  />
                ))}
              </>
            )}
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

// Permission/Authorization Mode Selector
export type PermissionMode = 'default' | 'auto_edit' | 'full_auto'

interface PermissionOption {
  id: PermissionMode
  name: string
  description: string
  icon: string
}

const PERMISSION_OPTIONS: PermissionOption[] = [
  { id: 'default', name: '默认', description: '每次操作前询问确认', icon: '◎' },
  { id: 'auto_edit', name: '自动编辑', description: '自动编辑文件，危险操作仍需确认', icon: '◉' },
  { id: 'full_auto', name: '全自动', description: '完全自主执行，无需确认', icon: '●' },
]

interface PermissionSelectorProps {
  compact?: boolean
}

export function PermissionSelector({ compact = false }: PermissionSelectorProps) {
  const { settings, updateSettings } = useAppStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const currentMode = PERMISSION_OPTIONS.find((p) => p.id === (settings as any).permissionMode) || PERMISSION_OPTIONS[0]

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectMode = (mode: PermissionMode) => {
    updateSettings({ permissionMode: mode } as any)
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
        <span>{currentMode.icon}</span>
        {!compact && <span>权限 · {currentMode.name}</span>}
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          className="absolute bottom-full mb-2 right-0 w-56 rounded-xl border border-border overflow-hidden animate-scale-in z-50"
          style={{ background: 'var(--dropdown-bg)', boxShadow: 'var(--dropdown-shadow)' }}
        >
          <div className="px-3 py-2 border-b border-border">
            <p className="text-[10px] font-semibold text-text-tertiary uppercase tracking-wider">授权模式</p>
          </div>
          <div className="py-1">
            {PERMISSION_OPTIONS.map((option) => (
              <button
                key={option.id}
                onClick={() => selectMode(option.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 transition-colors ${
                  option.id === currentMode.id
                    ? 'bg-primary-500/10 text-primary-500'
                    : 'text-text-primary hover:bg-surface-tertiary'
                }`}
              >
                <span className="text-sm">{option.icon}</span>
                <div className="flex-1 text-left">
                  <p className="text-xs font-medium">{option.name}</p>
                  <p className="text-[10px] text-text-tertiary">{option.description}</p>
                </div>
                {option.id === currentMode.id && <Check size={14} className="text-primary-500" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
