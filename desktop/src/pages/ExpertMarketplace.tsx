import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, Check, UserPlus, UserMinus, Plus, Star, Filter,
  MessageSquare, Zap
} from 'lucide-react'
import { useAppStore, Expert, ExpertCategory, EXPERT_CATEGORIES, BUILTIN_EXPERTS } from '../store'

export default function ExpertMarketplace() {
  const navigate = useNavigate()
  const { experts, hiredExpertIds, hireExpert, fireExpert, createSession } = useAppStore()
  const [selectedCategory, setSelectedCategory] = useState<ExpertCategory | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'all' | 'hired'>('all')

  // Filter experts
  const filtered = experts.filter((e) => {
    if (viewMode === 'hired' && !hiredExpertIds.includes(e.id)) return false
    if (selectedCategory !== 'all' && e.category !== selectedCategory) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      return e.name.toLowerCase().includes(q) || e.description.toLowerCase().includes(q)
    }
    return true
  })

  const hiredCount = hiredExpertIds.length

  // Start chat with expert
  const handleChatWithExpert = (expert: Expert) => {
    const sessionId = createSession(expert.id)
    navigate(`/chat/${sessionId}`)
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
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex items-center rounded-lg border border-border overflow-hidden" style={{ background: 'var(--surface-secondary)' }}>
              <button
                onClick={() => setViewMode('all')}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === 'all' ? 'bg-primary-500 text-white' : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                全部
              </button>
              <button
                onClick={() => setViewMode('hired')}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === 'hired' ? 'bg-primary-500 text-white' : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                已雇佣 ({hiredCount})
              </button>
            </div>
          </div>
        </div>

        {/* Search + Category filter */}
        <div className="flex items-center gap-3">
          {/* Search */}
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

          {/* Category pills */}
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
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Expert card component
function ExpertCard({
  expert, hired, onHire, onFire, onChat
}: {
  expert: Expert
  hired: boolean
  onHire: () => void
  onFire: () => void
  onChat: () => void
}) {
  const categoryInfo = EXPERT_CATEGORIES[expert.category]

  return (
    <div
      className={`relative rounded-xl border p-4 transition-all group ${
        hired
          ? 'border-primary-300 shadow-sm'
          : 'border-border hover:border-text-tertiary hover:shadow-sm'
      }`}
      style={{ background: 'var(--surface-secondary)' }}
    >
      {/* Hired badge */}
      {hired && (
        <div className="absolute top-3 right-3">
          <span className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium text-primary-500 bg-primary-500/10 rounded-full">
            <Check size={10} />
            已雇佣
          </span>
        </div>
      )}

      {/* Icon + Name */}
      <div className="flex items-start gap-3 mb-3">
        <div
          className="w-11 h-11 rounded-xl flex items-center justify-center text-xl shrink-0"
          style={{ background: 'var(--surface-tertiary)' }}
        >
          {expert.icon}
        </div>
        <div className="min-w-0">
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
      </div>
    </div>
  )
}
