import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Trash2, Play, Clock, Zap, Search,
  ChevronDown, ChevronRight, Edit2, Save, X, BookOpen
} from 'lucide-react'
import { useAppStore, SkillTemplate, ExpertCategory, EXPERT_CATEGORIES } from '../store'

export default function SkillLibrary() {
  const navigate = useNavigate()
  const { skillTemplates, removeSkillTemplate, updateSkillTemplate, experts } = useAppStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const filtered = skillTemplates.filter((s) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
  })

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: 'var(--surface-primary)' }}>
      {/* Header */}
      <div className="px-8 pt-6 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-text-primary">技能库</h1>
            <p className="text-sm text-text-tertiary mt-0.5">
              保存的工作流模板 · 一键复用或设为定时任务
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors"
          >
            <Plus size={14} />
            创建 Skill
          </button>
        </div>

        {/* Search */}
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg max-w-xs"
          style={{ background: 'var(--surface-tertiary)' }}
        >
          <Search size={14} className="text-text-tertiary shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索技能..."
            className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder-text-tertiary"
          />
        </div>
      </div>

      {/* Skill list */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
            <BookOpen size={40} className="mb-3 opacity-30" />
            <p className="text-sm">暂无保存的技能</p>
            <p className="text-xs mt-1 opacity-60">完成对话后可保存为技能模板</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((skill) => (
              <SkillCard
                key={skill.id}
                skill={skill}
                experts={experts}
                onRemove={() => removeSkillTemplate(skill.id)}
                onToggleAutowork={() => {
                  updateSkillTemplate(skill.id, {
                    autowork: skill.autowork?.enabled
                      ? { enabled: false }
                      : { enabled: true, cron: '0 * * * *' }
                  })
                }}
                onRun={() => {
                  // Execute skill - create session and run steps
                  const { createSession, addMessage } = useAppStore.getState()
                  const sessionId = createSession(skill.steps[0]?.expertId)
                  // Add first step as user message
                  if (skill.steps.length > 0) {
                    addMessage(sessionId, {
                      id: crypto.randomUUID(),
                      role: 'user',
                      content: `[执行技能: ${skill.name}]\n\n${skill.steps[0].prompt}`,
                      timestamp: Date.now()
                    })
                    useAppStore.getState().setPendingSessionId(sessionId)
                  }
                  navigate(`/chat/${sessionId}`)
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create modal */}
      {showCreate && <CreateSkillModal onClose={() => setShowCreate(false)} />}
    </div>
  )
}

function SkillCard({
  skill, experts, onRemove, onToggleAutowork, onRun
}: {
  skill: SkillTemplate
  experts: any[]
  onRemove: () => void
  onToggleAutowork: () => void
  onRun: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const categoryInfo = EXPERT_CATEGORIES[skill.category]

  return (
    <div
      className="rounded-xl border border-border overflow-hidden transition-all"
      style={{ background: 'var(--surface-secondary)' }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-text-tertiary shrink-0"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>

        <span className="text-xl shrink-0">{skill.icon}</span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-text-primary truncate">{skill.name}</h3>
            {skill.autowork?.enabled && (
              <span className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-accent-green bg-green-500/10 rounded-full">
                <Clock size={9} />
                自动
              </span>
            )}
          </div>
          <p className="text-xs text-text-tertiary truncate">{skill.description}</p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onRun}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors"
          >
            <Play size={11} />
            执行
          </button>
          <button
            onClick={onToggleAutowork}
            className={`p-2 rounded-lg transition-colors ${
              skill.autowork?.enabled
                ? 'text-accent-green bg-green-500/10'
                : 'text-text-tertiary hover:text-text-primary hover:bg-surface-tertiary'
            }`}
            title={skill.autowork?.enabled ? '关闭定时' : '设为定时'}
          >
            <Clock size={14} />
          </button>
          <button
            onClick={onRemove}
            className="p-2 text-text-tertiary hover:text-accent-red rounded-lg hover:bg-surface-tertiary transition-colors"
            title="删除"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Expanded: show steps */}
      {expanded && (
        <div className="px-5 pb-4 border-t border-border pt-3">
          <p className="text-[10px] text-text-tertiary uppercase tracking-wider mb-2 font-semibold">执行步骤</p>
          <div className="space-y-2">
            {skill.steps.map((step, i) => {
              const expert = experts.find((e) => e.id === step.expertId)
              return (
                <div
                  key={i}
                  className="flex items-start gap-2 px-3 py-2 rounded-lg"
                  style={{ background: 'var(--surface-tertiary)' }}
                >
                  <span className="text-sm shrink-0 mt-0.5">{expert?.icon || '⊙'}</span>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-text-primary">
                      {i + 1}. {expert?.name || step.expertId}
                    </p>
                    <p className="text-[11px] text-text-secondary mt-0.5 line-clamp-2">{step.prompt}</p>
                  </div>
                </div>
              )
            })}
          </div>
          <p className="text-[10px] text-text-tertiary mt-3">
            创建于 {new Date(skill.createdAt).toLocaleDateString('zh-CN')}
            {skill.category && ` · ${categoryInfo?.label}`}
          </p>
        </div>
      )}
    </div>
  )
}

// Create skill modal
function CreateSkillModal({ onClose }: { onClose: () => void }) {
  const { experts, hiredExpertIds, saveSkillTemplate } = useAppStore()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [icon, setIcon] = useState('⚡')
  const [category, setCategory] = useState<ExpertCategory>('content')
  const [steps, setSteps] = useState<Array<{ expertId: string; prompt: string }>>([
    { expertId: '', prompt: '' }
  ])

  const hiredExperts = experts.filter((e) => hiredExpertIds.includes(e.id))

  const addStep = () => {
    setSteps([...steps, { expertId: '', prompt: '' }])
  }

  const removeStep = (idx: number) => {
    setSteps(steps.filter((_, i) => i !== idx))
  }

  const updateStep = (idx: number, field: 'expertId' | 'prompt', value: string) => {
    setSteps(steps.map((s, i) => i === idx ? { ...s, [field]: value } : s))
  }

  const handleSave = () => {
    if (!name.trim() || steps.length === 0 || !steps[0].prompt.trim()) return
    saveSkillTemplate({
      name: name.trim(),
      description: description.trim(),
      icon,
      steps: steps.filter((s) => s.prompt.trim()),
      category,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-[600px] max-h-[80vh] rounded-2xl border border-border overflow-hidden flex flex-col animate-scale-in"
        style={{ background: 'var(--surface-primary)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-lg font-bold text-text-primary">创建技能模板</h3>
          <button onClick={onClose} className="p-1.5 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Name + Icon */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-medium text-text-secondary mb-1 block">名称</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：每日热点追踪"
                className="w-full px-3 py-2 rounded-lg text-sm text-text-primary placeholder-text-tertiary outline-none focus:ring-2 focus:ring-primary-500"
                style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
              />
            </div>
            <div className="w-20">
              <label className="text-xs font-medium text-text-secondary mb-1 block">图标</label>
              <input
                value={icon}
                onChange={(e) => setIcon(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm text-center text-text-primary outline-none focus:ring-2 focus:ring-primary-500"
                style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="text-xs font-medium text-text-secondary mb-1 block">描述</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="这个技能做什么..."
              className="w-full px-3 py-2 rounded-lg text-sm text-text-primary placeholder-text-tertiary outline-none focus:ring-2 focus:ring-primary-500"
              style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
            />
          </div>

          {/* Category */}
          <div>
            <label className="text-xs font-medium text-text-secondary mb-1 block">分类</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as ExpertCategory)}
              className="w-full px-3 py-2 rounded-lg text-sm text-text-primary outline-none focus:ring-2 focus:ring-primary-500"
              style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
            >
              {(Object.entries(EXPERT_CATEGORIES) as [ExpertCategory, { label: string; icon: string }][]).map(([key, { label, icon }]) => (
                <option key={key} value={key}>{icon} {label}</option>
              ))}
            </select>
          </div>

          {/* Steps */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-text-secondary">执行步骤</label>
              <button
                onClick={addStep}
                className="flex items-center gap-1 text-xs text-primary-500 hover:text-primary-600"
              >
                <Plus size={12} />
                添加步骤
              </button>
            </div>
            <div className="space-y-3">
              {steps.map((step, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg border border-border"
                  style={{ background: 'var(--surface-secondary)' }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-text-secondary">步骤 {i + 1}</span>
                    {steps.length > 1 && (
                      <button
                        onClick={() => removeStep(i)}
                        className="text-text-tertiary hover:text-accent-red"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                  <select
                    value={step.expertId}
                    onChange={(e) => updateStep(i, 'expertId', e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary mb-2 outline-none"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
                  >
                    <option value="">选择专家...</option>
                    {hiredExperts.map((e) => (
                      <option key={e.id} value={e.id}>{e.icon} {e.name}</option>
                    ))}
                    {/* Also show all experts */}
                    {experts.filter(e => !hiredExpertIds.includes(e.id)).map((e) => (
                      <option key={e.id} value={e.id}>{e.icon} {e.name} (未雇佣)</option>
                    ))}
                  </select>
                  <textarea
                    value={step.prompt}
                    onChange={(e) => updateStep(i, 'prompt', e.target.value)}
                    placeholder="给专家的指令..."
                    rows={2}
                    className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary placeholder-text-tertiary resize-none outline-none"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || !steps[0]?.prompt.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Save size={14} />
            保存
          </button>
        </div>
      </div>
    </div>
  )
}
