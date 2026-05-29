import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Play, Trash2, Clock, Edit2, Zap, Search } from 'lucide-react'
import { useAppStore, Workflow } from '../store'

export default function WorkflowList() {
  const navigate = useNavigate()
  const { workflows, removeWorkflow, addToast } = useAppStore()
  const [searchQuery, setSearchQuery] = useState('')

  const filtered = workflows.filter((w) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return w.name.toLowerCase().includes(q) || w.description.toLowerCase().includes(q)
  })

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: 'var(--surface-primary)' }}>
      <div className="px-8 pt-6 pb-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-text-primary">工作流</h1>
            <p className="text-sm text-text-tertiary mt-0.5">
              可视化编排多专家协作流程 · {workflows.length} 个工作流
            </p>
          </div>
          <button
            onClick={() => navigate('/workflows/new')}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors"
          >
            <Plus size={14} />
            新建工作流
          </button>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg max-w-xs"
          style={{ background: 'var(--surface-tertiary)' }}>
          <Search size={14} className="text-text-tertiary" />
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索工作流..." className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder-text-tertiary" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
            <Zap size={40} className="mb-3 opacity-30" />
            <p className="text-sm">暂无工作流</p>
            <p className="text-xs mt-1 opacity-60">点击「新建工作流」开始创建</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map((wf) => (
              <WorkflowCard key={wf.id} workflow={wf}
                onEdit={() => navigate(`/workflows/${wf.id}`)}
                onRemove={() => { removeWorkflow(wf.id); addToast({ type: 'success', title: '已删除' }) }}
                onRun={() => addToast({ type: 'info', title: '开始执行', description: wf.name })}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}


function WorkflowCard({ workflow, onEdit, onRemove, onRun }: {
  workflow: Workflow; onEdit: () => void; onRemove: () => void; onRun: () => void
}) {
  const expertNodes = workflow.nodes.filter(n => n.type === 'expert')
  const experts = useAppStore.getState().experts

  return (
    <div className="rounded-xl border border-border p-5 transition-all hover:shadow-md hover:border-text-tertiary group"
      style={{ background: 'var(--surface-secondary)' }}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{workflow.icon || '⚡'}</span>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{workflow.name}</h3>
            <p className="text-[10px] text-text-tertiary">
              {expertNodes.length} 个专家 · {workflow.nodes.length} 节点 · {workflow.edges.length} 连线
            </p>
          </div>
        </div>
        {workflow.autowork?.enabled && (
          <span className="flex items-center gap-1 px-1.5 py-0.5 text-[9px] text-accent-green bg-green-500/10 rounded-full">
            <Clock size={8} /> 定时
          </span>
        )}
      </div>

      {workflow.description && (
        <p className="text-xs text-text-secondary mb-3 line-clamp-2">{workflow.description}</p>
      )}

      {/* Expert icons */}
      {expertNodes.length > 0 && (
        <div className="flex items-center gap-1 mb-4">
          {expertNodes.slice(0, 5).map((node) => {
            const expert = experts.find(e => e.id === node.data.expertId)
            return (
              <span key={node.id} className="text-sm" title={expert?.name || node.data.label}>
                {expert?.icon || '🤖'}
              </span>
            )
          })}
          {expertNodes.length > 5 && <span className="text-[10px] text-text-tertiary">+{expertNodes.length - 5}</span>}
          <span className="text-[10px] text-text-tertiary ml-1">
            → {workflow.nodes.find(n => n.type === 'end') ? '结束' : '...'}
          </span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button onClick={onRun}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-accent-green rounded-lg hover:bg-green-600 transition-colors">
          <Play size={11} /> 运行
        </button>
        <button onClick={onEdit}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg border border-border text-text-secondary hover:text-text-primary hover:bg-surface-tertiary transition-colors">
          <Edit2 size={11} /> 编辑
        </button>
        <button onClick={onRemove}
          className="p-2 text-text-tertiary hover:text-accent-red rounded-lg hover:bg-surface-tertiary transition-colors opacity-0 group-hover:opacity-100">
          <Trash2 size={14} />
        </button>
      </div>

      <p className="text-[9px] text-text-tertiary mt-3">
        更新于 {new Date(workflow.updatedAt).toLocaleDateString('zh-CN')}
      </p>
    </div>
  )
}
