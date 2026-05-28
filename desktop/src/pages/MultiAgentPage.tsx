import { useState } from 'react'
import {
  Plus, Play, Square, RotateCcw, CheckCircle2, XCircle, Loader2,
  Clock, ChevronDown, ChevronRight, Bot, Trash2, GitBranch
} from 'lucide-react'
import DiffView, { DiffFile } from '../components/DiffView'

// Agent 任务状态
type TaskStatus = 'idle' | 'running' | 'completed' | 'failed' | 'stopped'

interface AgentTask {
  id: string
  name: string
  agentType: string
  prompt: string
  status: TaskStatus
  progress: number // 0-100
  startedAt?: number
  completedAt?: number
  output: string
  diffFiles?: DiffFile[]
}

// 示例数据
const defaultTasks: AgentTask[] = [
  {
    id: '1',
    name: '重构登录模块',
    agentType: 'python_developer',
    prompt: '将登录模块从函数式重构为类，添加错误处理和重试逻辑',
    status: 'completed',
    progress: 100,
    startedAt: Date.now() - 120000,
    completedAt: Date.now() - 5000,
    output: '已完成重构，修改了 3 个文件，添加了 AuthService 类。',
    diffFiles: [
      {
        filename: 'agent/auth/service.py',
        status: 'added',
        hunks: [{ oldStart: 0, newStart: 1, lines: [
          { type: 'add', content: 'class AuthService:', newLineNo: 1 },
          { type: 'add', content: '    def __init__(self, config):', newLineNo: 2 },
          { type: 'add', content: '        self.config = config', newLineNo: 3 },
          { type: 'add', content: '        self.max_retries = 3', newLineNo: 4 },
        ]}]
      },
      {
        filename: 'agent/auth/__init__.py',
        status: 'modified',
        hunks: [{ oldStart: 1, newStart: 1, lines: [
          { type: 'remove', content: 'from .login import login_user', oldLineNo: 1 },
          { type: 'add', content: 'from .service import AuthService', newLineNo: 1 },
        ]}]
      }
    ]
  },
  {
    id: '2',
    name: '添加单元测试',
    agentType: 'test_engineer',
    prompt: '为 AuthService 编写完整的单元测试，覆盖正常流程和异常场景',
    status: 'running',
    progress: 65,
    startedAt: Date.now() - 30000,
    output: '正在生成测试用例... 已完成 8/12 个测试...',
  },
  {
    id: '3',
    name: '安全审计',
    agentType: 'security_auditor',
    prompt: '审查 auth 模块的安全性，检查密码存储、SQL注入、XSS 等',
    status: 'idle',
    progress: 0,
    output: '',
  }
]

export default function MultiAgentPage() {
  const [tasks, setTasks] = useState<AgentTask[]>(defaultTasks)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>('1')
  const [showNewTask, setShowNewTask] = useState(false)

  const selectedTask = tasks.find(t => t.id === selectedTaskId)

  const startTask = (id: string) => {
    setTasks(tasks.map(t => t.id === id ? { ...t, status: 'running' as TaskStatus, startedAt: Date.now(), progress: 0 } : t))
  }

  const stopTask = (id: string) => {
    setTasks(tasks.map(t => t.id === id ? { ...t, status: 'stopped' as TaskStatus } : t))
  }

  const removeTask = (id: string) => {
    setTasks(tasks.filter(t => t.id !== id))
    if (selectedTaskId === id) setSelectedTaskId(null)
  }

  const addTask = (name: string, agentType: string, prompt: string) => {
    const newTask: AgentTask = {
      id: crypto.randomUUID(),
      name,
      agentType,
      prompt,
      status: 'idle',
      progress: 0,
      output: ''
    }
    setTasks([...tasks, newTask])
    setShowNewTask(false)
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* 左侧：任务列表 */}
      <div className="w-80 border-r border-gray-200 flex flex-col bg-white">
        {/* 顶部 */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-bold text-gray-800">多 Agent 并行</h2>
            <button
              onClick={() => setShowNewTask(true)}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
            >
              <Plus size={12} />
              新任务
            </button>
          </div>

          {/* 统计 */}
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              {tasks.filter(t => t.status === 'completed').length} 完成
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              {tasks.filter(t => t.status === 'running').length} 运行中
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-300" />
              {tasks.filter(t => t.status === 'idle').length} 待执行
            </span>
          </div>
        </div>

        {/* 任务列表 */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {tasks.map(task => (
            <TaskCard
              key={task.id}
              task={task}
              selected={selectedTaskId === task.id}
              onSelect={() => setSelectedTaskId(task.id)}
              onStart={() => startTask(task.id)}
              onStop={() => stopTask(task.id)}
              onRemove={() => removeTask(task.id)}
            />
          ))}
        </div>
      </div>

      {/* 右侧：任务详情 */}
      <div className="flex-1 overflow-y-auto bg-gray-50/50">
        {selectedTask ? (
          <TaskDetail task={selectedTask} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Bot size={48} className="mb-3 text-gray-300" />
            <p className="text-sm">选择一个任务查看详情</p>
            <p className="text-xs mt-1">或点击「新任务」创建并行 Agent 任务</p>
          </div>
        )}
      </div>

      {/* 新建任务弹窗 */}
      {showNewTask && (
        <NewTaskModal onClose={() => setShowNewTask(false)} onAdd={addTask} />
      )}
    </div>
  )
}

// 任务卡片
function TaskCard({
  task, selected, onSelect, onStart, onStop, onRemove
}: {
  task: AgentTask
  selected: boolean
  onSelect: () => void
  onStart: () => void
  onStop: () => void
  onRemove: () => void
}) {
  return (
    <div
      onClick={onSelect}
      className={`p-3 rounded-xl cursor-pointer transition-all ${
        selected
          ? 'bg-primary-50 border border-primary-200 shadow-sm'
          : 'bg-white border border-gray-100 hover:border-gray-200 hover:shadow-sm'
      }`}
    >
      {/* 顶部行 */}
      <div className="flex items-center gap-2 mb-2">
        <StatusIcon status={task.status} />
        <span className="text-sm font-medium text-gray-800 truncate flex-1">{task.name}</span>
        <button
          onClick={(e) => { e.stopPropagation(); onRemove() }}
          className="p-1 text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
        >
          <Trash2 size={12} />
        </button>
      </div>

      {/* Agent 类型 */}
      <p className="text-xs text-gray-500 mb-2 truncate">{task.prompt}</p>

      {/* 进度条 */}
      {task.status === 'running' && (
        <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary-500 rounded-full transition-all duration-500"
            style={{ width: `${task.progress}%` }}
          />
        </div>
      )}

      {/* 底部操作 */}
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-gray-400">
          {task.agentType}
        </span>
        <div className="flex items-center gap-1">
          {task.status === 'idle' && (
            <button
              onClick={(e) => { e.stopPropagation(); onStart() }}
              className="p-1 text-green-500 hover:text-green-600 transition-colors"
              title="启动"
            >
              <Play size={14} />
            </button>
          )}
          {task.status === 'running' && (
            <button
              onClick={(e) => { e.stopPropagation(); onStop() }}
              className="p-1 text-red-500 hover:text-red-600 transition-colors"
              title="停止"
            >
              <Square size={14} />
            </button>
          )}
          {(task.status === 'failed' || task.status === 'stopped') && (
            <button
              onClick={(e) => { e.stopPropagation(); onStart() }}
              className="p-1 text-blue-500 hover:text-blue-600 transition-colors"
              title="重试"
            >
              <RotateCcw size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// 任务详情
function TaskDetail({ task }: { task: AgentTask }) {
  const [showDiff, setShowDiff] = useState(true)

  const duration = task.startedAt
    ? Math.round(((task.completedAt || Date.now()) - task.startedAt) / 1000)
    : 0

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* 标题区 */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <StatusIcon status={task.status} size={20} />
          <h3 className="text-xl font-bold text-gray-800">{task.name}</h3>
        </div>
        <p className="text-sm text-gray-500">{task.prompt}</p>
      </div>

      {/* 状态信息 */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <InfoCard label="Agent 类型" value={task.agentType} icon={<Bot size={14} />} />
        <InfoCard label="状态" value={statusLabel(task.status)} icon={<StatusIcon status={task.status} size={14} />} />
        <InfoCard label="耗时" value={duration > 0 ? `${duration}s` : '-'} icon={<Clock size={14} />} />
      </div>

      {/* 输出 */}
      {task.output && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Agent 输出</h4>
          <div className="p-4 bg-white rounded-xl border border-gray-150 text-sm text-gray-700 whitespace-pre-wrap">
            {task.output}
            {task.status === 'running' && (
              <span className="inline-block w-2 h-4 bg-primary-400 animate-pulse rounded-sm ml-1" />
            )}
          </div>
        </div>
      )}

      {/* Diff 视图 */}
      {task.diffFiles && task.diffFiles.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <GitBranch size={14} />
              代码变更
            </h4>
            <button
              onClick={() => setShowDiff(!showDiff)}
              className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
            >
              {showDiff ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              {showDiff ? '收起' : '展开'}
            </button>
          </div>
          {showDiff && <DiffView files={task.diffFiles} title={`${task.name} 变更`} />}
        </div>
      )}
    </div>
  )
}

// 新建任务弹窗
function NewTaskModal({ onClose, onAdd }: { onClose: () => void; onAdd: (name: string, agentType: string, prompt: string) => void }) {
  const [name, setName] = useState('')
  const [agentType, setAgentType] = useState('python_developer')
  const [prompt, setPrompt] = useState('')

  const handleSubmit = () => {
    if (!name.trim() || !prompt.trim()) return
    onAdd(name.trim(), agentType, prompt.trim())
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-[500px] p-6" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold text-gray-800 mb-4">新建并行任务</h3>

        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">任务名称</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="例如：重构用户模块"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Agent 类型</label>
            <select
              value={agentType}
              onChange={e => setAgentType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="python_developer">Python 开发</option>
              <option value="code_reviewer">代码审查</option>
              <option value="test_engineer">测试工程师</option>
              <option value="security_auditor">安全审计</option>
              <option value="architect">架构师</option>
              <option value="bug_fixer">Bug 修复</option>
              <option value="full_stack">全栈开发</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">任务描述</label>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="详细描述你希望 Agent 完成的工作..."
              rows={4}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || !prompt.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:bg-gray-200 disabled:text-gray-400 transition-colors"
          >
            创建任务
          </button>
        </div>
      </div>
    </div>
  )
}

// 状态图标
function StatusIcon({ status, size = 16 }: { status: TaskStatus; size?: number }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 size={size} className="text-green-500" />
    case 'running':
      return <Loader2 size={size} className="text-blue-500 animate-spin" />
    case 'failed':
      return <XCircle size={size} className="text-red-500" />
    case 'stopped':
      return <Square size={size} className="text-orange-400" />
    default:
      return <Clock size={size} className="text-gray-400" />
  }
}

function statusLabel(status: TaskStatus): string {
  const map: Record<TaskStatus, string> = {
    idle: '待执行',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止'
  }
  return map[status]
}

function InfoCard({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="p-3 bg-white rounded-xl border border-gray-150">
      <div className="flex items-center gap-1.5 text-gray-400 mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p className="text-sm font-medium text-gray-800">{value}</p>
    </div>
  )
}
