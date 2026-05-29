import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, Check, UserPlus, UserMinus, Plus, Filter,
  MessageSquare, X, Save, Upload, RefreshCw
} from 'lucide-react'
import { useAppStore, Expert, ExpertCategory, EXPERT_CATEGORIES } from '../store'

// Source labels & colors
const SOURCE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  builtin: { label: '内置', color: 'text-text-tertiary', bg: 'bg-surface-tertiary' },
  backend: { label: '后端', color: 'text-accent-green', bg: 'bg-green-500/10' },
  custom: { label: '自定义', color: 'text-accent-amber', bg: 'bg-amber-500/10' },
  marketplace: { label: '市场', color: 'text-primary-500', bg: 'bg-primary-500/10' },
}

export default function ExpertMarketplace() {
  const navigate = useNavigate()
  const { experts, hiredExpertIds, hireExpert, fireExpert, createSession, addCustomExpert, removeCustomExpert } = useAppStore()
  const [selectedCategory, setSelectedCategory] = useState<ExpertCategory | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'all' | 'hired' | 'custom' | 'marketplace'>('all')
  const [showCreateExpert, setShowCreateExpert] = useState(false)

  // Filter experts
  const filtered = experts.filter((e) => {
    if (viewMode === 'hired' && !hiredExpertIds.includes(e.id)) return false
    if (viewMode === 'custom' && e.source !== 'custom') return false
    if (viewMode === 'marketplace' && e.source !== 'marketplace') return false
    if (selectedCategory !== 'all' && e.category !== selectedCategory) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      return e.name.toLowerCase().includes(q) || e.description.toLowerCase().includes(q) ||
        e.capabilities.some(c => c.toLowerCase().includes(q))
    }
    return true
  })

  const hiredCount = hiredExpertIds.length
  const customCount = experts.filter(e => e.source === 'custom').length
  const marketCount = experts.filter(e => e.source === 'marketplace').length
  const backendCount = experts.filter(e => e.source === 'backend').length

  // Start chat with expert
  const handleChatWithExpert = (expert: Expert) => {
    const sessionId = createSession(expert.id)
    navigate(`/chat/${sessionId}`)
  }

  // Refresh experts from all sources
  const handleRefresh = () => {
    useAppStore.getState().fetchExperts()
  }

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: 'var(--surface-primary)' }}>
      {/* Header */}
      <div className="px-8 pt-6 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-text-primary">专家市场</h1>
            <p className="text-sm text-text-tertiary mt-0.5">
              雇佣 AI 专家加入你的团队 · 已雇佣 {hiredCount} 位
              {backendCount > 0 && <span className="ml-2 text-accent-green">· {backendCount} 后端</span>}
              {marketCount > 0 && <span className="ml-2 text-primary-500">· {marketCount} 市场</span>}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors"
              title="刷新（从后端+市场重新拉取）"
            >
              <RefreshCw size={16} />
            </button>
            <button
              onClick={() => setShowCreateExpert(true)}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors"
            >
              <Plus size={14} />
              创建专家
            </button>
          </div>
        </div>

        {/* View tabs */}
        <div className="flex items-center gap-3 mb-3">
          <div className="flex items-center rounded-lg border border-border overflow-hidden" style={{ background: 'var(--surface-secondary)' }}>
            <TabButton active={viewMode === 'all'} onClick={() => setViewMode('all')} label="全部" count={experts.length} />
            <TabButton active={viewMode === 'hired'} onClick={() => setViewMode('hired')} label="已雇佣" count={hiredCount} />
            <TabButton active={viewMode === 'custom'} onClick={() => setViewMode('custom')} label="自定义" count={customCount} />
            <TabButton active={viewMode === 'marketplace'} onClick={() => setViewMode('marketplace')} label="市场" count={marketCount} />
          </div>
        </div>

        {/* Search + Category filter */}
        <div className="flex items-center gap-3">
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg flex-1 max-w-xs"
            style={{ background: 'var(--surface-tertiary)' }}
          >
            <Search size={14} className="text-text-tertiary shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索专家..."
              className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder-text-tertiary"
            />
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto">
            <button
              onClick={() => setSelectedCategory('all')}
              className={`shrink-0 px-3 py-1.5 text-xs rounded-full border transition-colors ${
                selectedCategory === 'all'
                  ? 'border-primary-500 bg-primary-500/10 text-primary-500 font-medium'
                  : 'border-border text-text-secondary hover:border-text-tertiary'
              }`}
            >
              全部
            </button>
            {(Object.entries(EXPERT_CATEGORIES) as [ExpertCategory, { label: string; icon: string }][]).map(
              ([key, { label, icon }]) => (
                <button
                  key={key}
                  onClick={() => setSelectedCategory(key)}
                  className={`shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs rounded-full border transition-colors ${
                    selectedCategory === key
                      ? 'border-primary-500 bg-primary-500/10 text-primary-500 font-medium'
                      : 'border-border text-text-secondary hover:border-text-tertiary'
                  }`}
                >
                  <span>{icon}</span>
                  <span>{label}</span>
                </button>
              )
            )}
          </div>
        </div>
      </div>

      {/* Expert grid */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
            <Search size={40} className="mb-3 opacity-30" />
            <p className="text-sm">无匹配专家</p>
            {viewMode === 'marketplace' && marketCount === 0 && (
              <p className="text-xs mt-2 opacity-60">请在设置中配置外部市场 API 地址</p>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map((expert) => (
              <ExpertCard
                key={expert.id}
                expert={expert}
                hired={hiredExpertIds.includes(expert.id)}
                onHire={() => hireExpert(expert.id)}
                onFire={() => fireExpert(expert.id)}
                onChat={() => handleChatWithExpert(expert)}
                onRemove={expert.source === 'custom' ? () => removeCustomExpert(expert.id) : undefined}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create expert modal */}
      {showCreateExpert && (
        <CreateExpertModal
          onClose={() => setShowCreateExpert(false)}
          onCreate={(expert) => {
            addCustomExpert(expert)
            setShowCreateExpert(false)
            useAppStore.getState().addToast({ type: 'success', title: '专家已创建', description: expert.name })
          }}
        />
      )}
    </div>
  )
}

// Tab button
function TabButton({ active, onClick, label, count }: { active: boolean; onClick: () => void; label: string; count: number }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium transition-colors ${
        active ? 'bg-primary-500 text-white' : 'text-text-secondary hover:text-text-primary'
      }`}
    >
      {label} {count > 0 && <span className="opacity-70">({count})</span>}
    </button>
  )
}

// Expert card
function ExpertCard({
  expert, hired, onHire, onFire, onChat, onRemove
}: {
  expert: Expert
  hired: boolean
  onHire: () => void
  onFire: () => void
  onChat: () => void
  onRemove?: () => void
}) {
  const categoryInfo = EXPERT_CATEGORIES[expert.category]
  const sourceInfo = SOURCE_LABELS[expert.source] || SOURCE_LABELS.builtin

  return (
    <div
      className={`relative rounded-xl border p-4 transition-all group ${
        hired
          ? 'border-primary-300 shadow-sm'
          : 'border-border hover:border-text-tertiary hover:shadow-sm'
      }`}
      style={{ background: 'var(--surface-secondary)' }}
    >
      {/* Source + Hired badges */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        <span className={`px-1.5 py-0.5 text-[9px] font-medium rounded-full ${sourceInfo.color} ${sourceInfo.bg}`}>
          {sourceInfo.label}
        </span>
        {hired && (
          <span className="flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-medium text-primary-500 bg-primary-500/10 rounded-full">
            <Check size={8} />
            已雇
          </span>
        )}
      </div>

      {/* Icon + Name */}
      <div className="flex items-start gap-3 mb-3 mt-1">
        <div
          className="w-11 h-11 rounded-xl flex items-center justify-center text-xl shrink-0"
          style={{ background: 'var(--surface-tertiary)' }}
        >
          {expert.icon}
        </div>
        <div className="min-w-0 pt-0.5">
          <h3 className="text-sm font-semibold text-text-primary truncate">{expert.name}</h3>
          <span className="text-[10px] text-text-tertiary">
            {categoryInfo?.icon} {categoryInfo?.label}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-text-secondary mb-3 line-clamp-2 leading-relaxed">
        {expert.description}
      </p>

      {/* Capabilities */}
      <div className="flex flex-wrap gap-1 mb-4">
        {expert.capabilities.slice(0, 3).map((cap) => (
          <span
            key={cap}
            className="px-2 py-0.5 text-[10px] rounded-md text-text-tertiary"
            style={{ background: 'var(--surface-tertiary)' }}
          >
            {cap}
          </span>
        ))}
        {expert.capabilities.length > 3 && (
          <span className="px-2 py-0.5 text-[10px] text-text-tertiary">
            +{expert.capabilities.length - 3}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {hired ? (
          <>
            <button
              onClick={onChat}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors"
            >
              <MessageSquare size={12} />
              对话
            </button>
            <button
              onClick={onFire}
              className="p-2 text-text-tertiary hover:text-accent-red rounded-lg hover:bg-surface-tertiary transition-colors"
              title="解雇"
            >
              <UserMinus size={14} />
            </button>
          </>
        ) : (
          <button
            onClick={onHire}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-border text-text-secondary hover:text-primary-500 hover:border-primary-300 hover:bg-primary-500/5 transition-colors"
          >
            <UserPlus size={12} />
            雇佣
          </button>
        )}
        {onRemove && (
          <button
            onClick={onRemove}
            className="p-2 text-text-tertiary hover:text-accent-red rounded-lg hover:bg-surface-tertiary transition-colors opacity-0 group-hover:opacity-100"
            title="删除自定义专家"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}

// ============ Create Expert Modal ============
function CreateExpertModal({
  onClose, onCreate
}: {
  onClose: () => void
  onCreate: (expert: Omit<Expert, 'id' | 'source'>) => void
}) {
  const [mode, setMode] = useState<'form' | 'yaml'>('form')
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('🤖')
  const [category, setCategory] = useState<ExpertCategory>('development')
  const [description, setDescription] = useState('')
  const [capabilities, setCapabilities] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [tools, setTools] = useState('')
  const [model, setModel] = useState('')
  const [yamlContent, setYamlContent] = useState('')

  const handleSubmitForm = () => {
    if (!name.trim() || !description.trim()) return
    onCreate({
      name: name.trim(),
      icon,
      category,
      description: description.trim(),
      capabilities: capabilities.split(/[,，\n]/).map(s => s.trim()).filter(Boolean),
      systemPrompt: systemPrompt.trim() || undefined,
      tools: tools.split(/[,，\n]/).map(s => s.trim()).filter(Boolean),
      model: model.trim() || undefined,
    })
  }

  const handleSubmitYaml = () => {
    if (!yamlContent.trim()) return
    try {
      // Simple YAML-like parsing (key: value per line)
      const lines = yamlContent.split('\n')
      const data: Record<string, string> = {}
      let currentKey = ''
      let multilineValue = ''

      for (const line of lines) {
        const match = line.match(/^(\w+):\s*(.*)$/)
        if (match) {
          if (currentKey && multilineValue) {
            data[currentKey] = multilineValue.trim()
          }
          currentKey = match[1]
          multilineValue = match[2] || ''
        } else if (currentKey && (line.startsWith('  ') || line.startsWith('\t'))) {
          multilineValue += '\n' + line.trim()
        }
      }
      if (currentKey && multilineValue) {
        data[currentKey] = multilineValue.trim()
      }

      if (!data.name) {
        useAppStore.getState().addToast({ type: 'error', title: '解析失败', description: 'YAML 中缺少 name 字段' })
        return
      }

      onCreate({
        name: data.name,
        icon: data.icon || '🤖',
        category: (data.category as ExpertCategory) || 'development',
        description: data.description || '',
        capabilities: (data.capabilities || data.tags || '').split(/[,，\n\-]/).map(s => s.trim()).filter(Boolean),
        systemPrompt: data.system_prompt || data.systemPrompt || '',
        tools: (data.tools || '').split(/[,，\n\-]/).map(s => s.trim()).filter(Boolean),
        model: data.model || undefined,
      })
    } catch {
      useAppStore.getState().addToast({ type: 'error', title: '解析失败', description: '请检查 YAML 格式' })
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-[620px] max-h-[85vh] rounded-2xl border border-border overflow-hidden flex flex-col animate-scale-in"
        style={{ background: 'var(--surface-primary)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="text-lg font-bold text-text-primary">创建自定义专家</h3>
          <button onClick={onClose} className="p-1.5 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary">
            <X size={18} />
          </button>
        </div>

        {/* Mode toggle */}
        <div className="flex items-center gap-2 px-6 pt-4">
          <button
            onClick={() => setMode('form')}
            className={`px-4 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              mode === 'form' ? 'bg-primary-500 text-white' : 'text-text-secondary hover:bg-surface-tertiary'
            }`}
          >
            表单创建
          </button>
          <button
            onClick={() => setMode('yaml')}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              mode === 'yaml' ? 'bg-primary-500 text-white' : 'text-text-secondary hover:bg-surface-tertiary'
            }`}
          >
            <Upload size={12} />
            YAML 导入
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {mode === 'form' ? (
            <div className="space-y-4">
              {/* Name + Icon */}
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="text-xs font-medium text-text-secondary mb-1 block">名称 *</label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="例如：视频导演"
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

              {/* Description */}
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">描述 *</label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="这位专家的核心能力..."
                  className="w-full px-3 py-2 rounded-lg text-sm text-text-primary placeholder-text-tertiary outline-none focus:ring-2 focus:ring-primary-500"
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
                />
              </div>

              {/* Capabilities */}
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">能力标签（逗号分隔）</label>
                <input
                  value={capabilities}
                  onChange={(e) => setCapabilities(e.target.value)}
                  placeholder="例如：分镜设计, 转场编排, 音画同步"
                  className="w-full px-3 py-2 rounded-lg text-sm text-text-primary placeholder-text-tertiary outline-none focus:ring-2 focus:ring-primary-500"
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
                />
              </div>

              {/* System Prompt */}
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">System Prompt</label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="定义专家的行为规则和知识范围...&#10;&#10;例如：你是一位专业的视频导演，精通分镜拆解..."
                  rows={5}
                  className="w-full px-3 py-2 rounded-lg text-sm text-text-primary placeholder-text-tertiary resize-none outline-none focus:ring-2 focus:ring-primary-500"
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
                />
              </div>

              {/* Tools */}
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">工具（逗号分隔，可选）</label>
                <input
                  value={tools}
                  onChange={(e) => setTools(e.target.value)}
                  placeholder="例如：file_read, file_write, bash_execute, web_search"
                  className="w-full px-3 py-2 rounded-lg text-sm text-text-primary placeholder-text-tertiary outline-none focus:ring-2 focus:ring-primary-500"
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
                />
              </div>

              {/* Model preference */}
              <div>
                <label className="text-xs font-medium text-text-secondary mb-1 block">偏好模型（可选）</label>
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="例如：gpt-4o 或 claude-sonnet-4-20250514"
                  className="w-full px-3 py-2 rounded-lg text-sm text-text-primary placeholder-text-tertiary outline-none focus:ring-2 focus:ring-primary-500"
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
                />
              </div>
            </div>
          ) : (
            /* YAML mode */
            <div className="space-y-3">
              <p className="text-xs text-text-tertiary">
                粘贴 YAML 格式的专家定义，支持与后端 <code className="px-1 rounded" style={{ background: 'var(--surface-tertiary)' }}>skills/presets/*.yaml</code> 相同的格式：
              </p>
              <div className="px-3 py-2 rounded-lg text-[11px] font-mono text-text-tertiary leading-relaxed" style={{ background: 'var(--surface-tertiary)' }}>
                name: video_director<br/>
                icon: 🎬<br/>
                category: media<br/>
                description: 视频导演 - 分镜拆解与视觉编排<br/>
                capabilities: 分镜设计, 转场编排, 音画同步<br/>
                model: gpt-4o<br/>
                tools: file_read, file_write, web_search<br/>
                system_prompt: |<br/>
                &nbsp;&nbsp;你是一位专业视频导演...
              </div>
              <textarea
                value={yamlContent}
                onChange={(e) => setYamlContent(e.target.value)}
                placeholder="粘贴 YAML 内容..."
                rows={12}
                className="w-full px-3 py-2 rounded-lg text-xs font-mono text-text-primary placeholder-text-tertiary resize-none outline-none focus:ring-2 focus:ring-primary-500"
                style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
              />
            </div>
          )}
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
            onClick={mode === 'form' ? handleSubmitForm : handleSubmitYaml}
            disabled={mode === 'form' ? (!name.trim() || !description.trim()) : !yamlContent.trim()}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Save size={14} />
            {mode === 'form' ? '创建专家' : '导入'}
          </button>
        </div>
      </div>
    </div>
  )
}
