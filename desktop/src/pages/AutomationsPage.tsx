import { useState } from 'react'
import {
  Plus, Play, Pause, Trash2, Pencil, Clock, Calendar,
  CheckCircle2, XCircle, ToggleRight, ToggleLeft,
  Zap, GitPullRequest, AlertTriangle, FileSearch, RefreshCw
} from 'lucide-react'

type AutomationStatus = 'active' | 'paused' | 'error'
type TriggerType = 'cron' | 'event' | 'interval'

interface Automation {
  id: string
  name: string
  description: string
  trigger: TriggerType
  schedule: string // cron expression or interval description
  agentType: string
  enabled: boolean
  status: AutomationStatus
  lastRun?: number
  lastResult?: 'success' | 'failure'
  nextRun?: number
  runCount: number
  icon: React.ReactNode
}

const defaultAutomations: Automation[] = [
  {
    id: '1',
    name: 'Issue 自动分类',
    description: '监控新 Issue，自动标注标签并分配负责人',
    trigger: 'event',
    schedule: '新 Issue 创建时触发',
    agentType: 'code_reviewer',
    enabled: true,
    status: 'active',
    lastRun: Date.now() - 3600000,
    lastResult: 'success',
    nextRun: undefined,
    runCount: 47,
    icon: <GitPullRequest size={18} className="text-purple-500" />
  },
  {
    id: '2',
    name: '每日安全扫描',
    description: '每天凌晨 2 点对代码库进行安全漏洞扫描',
    trigger: 'cron',
    schedule: '0 2 * * *',
    agentType: 'security_auditor',
    enabled: true,
    status: 'active',
    lastRun: Date.now() - 86400000,
    lastResult: 'success',
    nextRun: Date.now() + 43200000,
    runCount: 30,
    icon: <AlertTriangle size={18} className="text-orange-500" />
  },
  {
    id: '3',
    name: 'CI/CD 失败告警',
    description: '监控 CI 流水线，失败时自动分析原因并通知',
    trigger: 'event',
    schedule: 'CI 失败时触发',
    agentType: 'devops_agent',
    enabled: true,
    status: 'active',
    lastRun: Date.now() - 7200000,
    lastResult: 'failure',
    runCount: 12,
    icon: <RefreshCw size={18} className="text-blue-500" />
  },
  {
    id: '4',
    name: '代码质量周报',
    description: '每周一生成代码质量报告，包含复杂度、覆盖率、技术债务分析',
    trigger: 'cron',
    schedule: '0 9 * * 1',
    agentType: 'code_reviewer',
    enabled: false,
    status: 'paused',
    lastRun: Date.now() - 604800000,
    lastResult: 'success',
    nextRun: undefined,
    runCount: 8,
    icon: <FileSearch size={18} className="text-green-500" />
  }
]

export default function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[]>(defaultAutomations)
  const [showNew, setShowNew] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)

  const toggleEnabled = (id: string) => {
    setAutomations(automations.map(a => {
      if (a.id !== id) return a
      const enabled = !a.enabled
      return { ...a, enabled, status: enabled ? 'active' : 'paused' }
    }))
  }

  const removeAutomation = (id: string) => {
    setAutomations(automations.filter(a => a.id !== id))
  }

  const runNow = (id: string) => {
    setAutomations(automations.map(a =>
      a.id === id ? { ...a, lastRun: Date.now(), runCount: a.runCount + 1, lastResult: 'success' as const } : a
    ))
  }

  const activeCount = automations.filter(a => a.enabled).length
  const totalRuns = automations.reduce((sum, a) => sum + a.runCount, 0)

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-800">自动化任务</h2>
            <p className="text-sm text-gray-500 mt-1">让 Agent 自动处理重复性工作</p>
          </div>
          <button
            onClick={() => setShowNew(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors shadow-sm"
          >
            <Plus size={14} />
            创建自动化
          </button>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard
            label="活跃任务"
            value={activeCount.toString()}
            sub={`共 ${automations.length} 个`}
            color="text-green-600"
            icon={<Zap size={16} className="text-green-500" />}
          />
          <StatCard
            label="总执行次数"
            value={totalRuns.toString()}
            sub="累计"
            color="text-blue-600"
            icon={<Play size={16} className="text-blue-500" />}
          />
          <StatCard
            label="最近执行"
            value={getRelativeTime(Math.max(...automations.filter(a => a.lastRun).map(a => a.lastRun!)))}
            sub="前"
            color="text-gray-600"
            icon={<Clock size={16} className="text-gray-500" />}
          />
        </div>

        {/* 提示 */}
        <div className="mb-5 px-4 py-3 bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl border border-amber-100">
          <p className="text-sm text-amber-700">
            自动化任务在后台持续运行，Agent 会按照设定的规则自动执行。支持 Cron 表达式、事件触发和固定间隔。
          </p>
        </div>

        {/* 自动化列表 */}
        <div className="space-y-3">
          {automations.map(automation => (
            <AutomationCard
              key={automation.id}
              automation={automation}
              onToggle={() => toggleEnabled(automation.id)}
              onRemove={() => removeAutomation(automation.id)}
              onRunNow={() => runNow(automation.id)}
              onEdit={() => setEditingId(automation.id)}
            />
          ))}
        </div>

        {automations.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <Clock size={48} className="mx-auto mb-3 text-gray-300" />
            <p className="text-sm">还没有自动化任务</p>
            <p className="text-xs mt-1">点击「创建自动化」开始</p>
          </div>
        )}
      </div>

      {/* 新建弹窗 */}
      {showNew && (
        <NewAutomationModal
          onClose={() => setShowNew(false)}
          onAdd={(a) => {
            setAutomations([...automations, a])
            setShowNew(false)
          }}
        />
      )}
    </div>
  )
}

// 自动化卡片
function AutomationCard({
  automation, onToggle, onRemove, onRunNow, onEdit
}: {
  automation: Automation
  onToggle: () => void
  onRemove: () => void
  onRunNow: () => void
  onEdit: () => void
}) {
  return (
    <div className={`p-4 bg-white rounded-xl border transition-all ${
      automation.enabled ? 'border-gray-150 hover:border-gray-200' : 'border-gray-100 opacity-60'
    }`}>
      <div className="flex items-start gap-4">
        {/* 图标 */}
        <div className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center shrink-0">
          {automation.icon}
        </div>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-sm font-semibold text-gray-800">{automation.name}</h4>
            {automation.lastResult === 'failure' && (
              <span className="px-1.5 py-0.5 text-xs bg-red-50 text-red-600 rounded">上次失败</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mb-2">{automation.description}</p>

          {/* 触发规则 + 统计 */}
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <TriggerIcon trigger={automation.trigger} />
              {automation.schedule}
            </span>
            <span>已运行 {automation.runCount} 次</span>
            {automation.lastRun && (
              <span>上次: {getRelativeTime(automation.lastRun)}前</span>
            )}
          </div>
        </div>

        {/* 右侧操作 */}
        <div className="flex items-center gap-2 shrink-0">
          {/* 立即运行 */}
          <button
            onClick={onRunNow}
            className="p-1.5 text-gray-400 hover:text-green-500 transition-colors rounded-lg hover:bg-green-50"
            title="立即运行"
          >
            <Play size={14} />
          </button>
          {/* 编辑 */}
          <button
            onClick={onEdit}
            className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors rounded-lg hover:bg-gray-50"
            title="编辑"
          >
            <Pencil size={14} />
          </button>
          {/* 删除 */}
          <button
            onClick={onRemove}
            className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded-lg hover:bg-red-50"
            title="删除"
          >
            <Trash2 size={14} />
          </button>
          {/* 开关 */}
          <button
            onClick={onToggle}
            className={`p-1 transition-colors ${automation.enabled ? 'text-primary-500' : 'text-gray-300'}`}
          >
            {automation.enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
          </button>
        </div>
      </div>
    </div>
  )
}

// 新建自动化弹窗
function NewAutomationModal({ onClose, onAdd }: {
  onClose: () => void
  onAdd: (a: Automation) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [trigger, setTrigger] = useState<TriggerType>('cron')
  const [schedule, setSchedule] = useState('')
  const [agentType, setAgentType] = useState('code_reviewer')

  const handleSubmit = () => {
    if (!name.trim() || !schedule.trim()) return
    onAdd({
      id: crypto.randomUUID(),
      name: name.trim(),
      description: description.trim(),
      trigger,
      schedule: schedule.trim(),
      agentType,
      enabled: true,
      status: 'active',
      runCount: 0,
      icon: <Zap size={18} className="text-primary-500" />
    })
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-[520px] p-6" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-gray-800 mb-4">创建自动化任务</h3>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">任务名称</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="例如：每日代码审查"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">描述</label>
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="简要描述这个自动化做什么"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">触发方式</label>
              <select
                value={trigger}
                onChange={e => setTrigger(e.target.value as TriggerType)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="cron">定时 (Cron)</option>
                <option value="event">事件触发</option>
                <option value="interval">固定间隔</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Agent 类型</label>
              <select
                value={agentType}
                onChange={e => setAgentType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="code_reviewer">代码审查</option>
                <option value="security_auditor">安全审计</option>
                <option value="devops_agent">DevOps</option>
                <option value="test_engineer">测试工程师</option>
                <option value="python_developer">Python 开发</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">
              {trigger === 'cron' ? 'Cron 表达式' : trigger === 'event' ? '触发事件' : '间隔时间'}
            </label>
            <input
              value={schedule}
              onChange={e => setSchedule(e.target.value)}
              placeholder={
                trigger === 'cron' ? '0 2 * * * (每天凌晨2点)' :
                trigger === 'event' ? '新 Issue 创建时' :
                '每 30 分钟'
              }
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            {trigger === 'cron' && (
              <p className="text-xs text-gray-400 mt-1">格式：分 时 日 月 周 (例: 0 9 * * 1 = 每周一9点)</p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || !schedule.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:bg-gray-200 disabled:text-gray-400 transition-colors"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  )
}

// 工具组件
function StatCard({ label, value, sub, color, icon }: {
  label: string; value: string; sub: string; color: string; icon: React.ReactNode
}) {
  return (
    <div className="p-4 bg-white rounded-xl border border-gray-150">
      <div className="flex items-center gap-1.5 text-gray-400 mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-400">{sub}</p>
    </div>
  )
}

function TriggerIcon({ trigger }: { trigger: TriggerType }) {
  switch (trigger) {
    case 'cron': return <Calendar size={12} />
    case 'event': return <Zap size={12} />
    case 'interval': return <RefreshCw size={12} />
  }
}

function getRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时`
  const days = Math.floor(hours / 24)
  return `${days} 天`
}
