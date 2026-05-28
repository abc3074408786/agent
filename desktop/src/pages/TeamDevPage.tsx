import { useState, useRef, useEffect } from 'react'
import {
  Target, Loader2, CheckCircle2, XCircle, Clock, Send, Square,
  Bot, ChevronDown, ChevronRight, Zap
} from 'lucide-react'

// ============ 类型定义 ============

type SubTaskStatus = 'pending' | 'running' | 'completed' | 'failed'

interface SubTask {
  id: string
  title: string
  description: string
  role: string
  roleIcon: string
  roleLabel: string
  roleColor: string
  model: string
  dependsOn: string[]
  status: SubTaskStatus
  output?: string
  durationMs?: number
}

interface TaskPlan {
  summary: string
  subtasks: SubTask[]
}

interface Message {
  id: string
  role: 'user' | 'leader' | 'agent' | 'system'
  content: string
  sender?: string
  timestamp: number
}

type TeamStatus = 'idle' | 'planning' | 'executing' | 'completed' | 'error'

// ============ 角色信息 ============

const ROLE_INFO: Record<string, { icon: string; label: string; color: string }> = {
  architect: { icon: '🏗️', label: '架构师', color: '#FF9800' },
  python_dev: { icon: '🐍', label: 'Python 开发', color: '#3776AB' },
  backend_dev: { icon: '🔧', label: '后端开发', color: '#68A063' },
  frontend_dev: { icon: '⚛️', label: '前端开发', color: '#61DAFB' },
  test_engineer: { icon: '🧪', label: '测试工程师', color: '#E535AB' },
  security_auditor: { icon: '🛡️', label: '安全审计', color: '#FF6B6B' },
  devops: { icon: '🚀', label: 'DevOps', color: '#2196F3' },
  database_expert: { icon: '🗄️', label: '数据库专家', color: '#4CAF50' },
  code_reviewer: { icon: '👁️', label: '代码审查', color: '#9C27B0' },
}

// ============ 模拟执行逻辑 ============

function decomposeTask(userMessage: string): TaskPlan {
  const msg = userMessage.toLowerCase()
  const hasAuth = ['登录', '注册', '认证', '鉴权', '验证', '邮箱'].some(k => msg.includes(k))
  const hasApi = ['api', '接口', '服务', '后端'].some(k => msg.includes(k))
  const hasFrontend = ['前端', '页面', 'ui', '组件'].some(k => msg.includes(k))
  const hasDb = ['数据库', '表', 'model'].some(k => msg.includes(k))

  const subtasks: SubTask[] = []

  // 架构设计
  const archId = crypto.randomUUID().slice(0, 8)
  subtasks.push({
    id: archId,
    title: '架构设计',
    description: `为「${userMessage}」设计系统架构`,
    role: 'architect',
    roleIcon: '🏗️',
    roleLabel: '架构师',
    roleColor: '#FF9800',
    model: 'claude-sonnet-4',
    dependsOn: [],
    status: 'pending',
  })

  // 代码实现
  const implId = crypto.randomUUID().slice(0, 8)
  subtasks.push({
    id: implId,
    title: hasApi || hasAuth ? '实现 API' + (hasAuth ? ' (含认证)' : '') : '代码实现',
    description: '根据架构设计实现核心功能',
    role: hasApi ? 'backend_dev' : 'python_dev',
    roleIcon: hasApi ? '🔧' : '🐍',
    roleLabel: hasApi ? '后端开发' : 'Python 开发',
    roleColor: hasApi ? '#68A063' : '#3776AB',
    model: 'gpt-4o',
    dependsOn: [archId],
    status: 'pending',
  })

  // 测试
  const testId = crypto.randomUUID().slice(0, 8)
  subtasks.push({
    id: testId,
    title: '编写测试',
    description: '编写单元测试和集成测试',
    role: 'test_engineer',
    roleIcon: '🧪',
    roleLabel: '测试工程师',
    roleColor: '#E535AB',
    model: 'claude-sonnet-4',
    dependsOn: [implId],
    status: 'pending',
  })

  // 安全审计（如果有认证相关）
  if (hasAuth) {
    subtasks.push({
      id: crypto.randomUUID().slice(0, 8),
      title: '安全审计',
      description: '检查认证流程安全性',
      role: 'security_auditor',
      roleIcon: '🛡️',
      roleLabel: '安全审计',
      roleColor: '#FF6B6B',
      model: 'gpt-4o',
      dependsOn: [implId],
      status: 'pending',
    })
  }

  let summary = `好的，我把这个任务拆解为 ${subtasks.length} 个子任务：\n`
  subtasks.forEach((st, i) => {
    summary += `  ${i + 1}. ${st.title} → ${st.roleIcon} ${st.roleLabel}\n`
  })

  return { summary, subtasks }
}

// Mock 输出
const MOCK_OUTPUTS: Record<string, string> = {
  architect: `## 架构设计方案\n\n### 模块划分\n1. **API 层** - FastAPI 路由和请求处理\n2. **业务逻辑层** - 核心业务逻辑\n3. **数据访问层** - 数据库操作\n\n### 技术选型\n- 框架: FastAPI + Pydantic\n- 数据库: PostgreSQL\n- 认证: JWT + bcrypt`,
  python_dev: `## 代码实现\n\n\`\`\`python\nfrom fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel, EmailStr\nfrom passlib.context import CryptContext\n\napp = FastAPI()\npwd_context = CryptContext(schemes=["bcrypt"])\n\nclass UserRegister(BaseModel):\n    email: EmailStr\n    password: str\n\n@app.post("/api/v1/register")\nasync def register(user: UserRegister):\n    hashed = pwd_context.hash(user.password)\n    return {"message": "注册成功"}\n\`\`\``,
  backend_dev: `## 后端 API 实现\n\n\`\`\`python\n@app.post("/api/v1/register")\nasync def register(user: UserRegister, bg: BackgroundTasks):\n    existing = await db.execute(select(User).where(User.email == user.email))\n    if existing.scalar():\n        raise HTTPException(400, "邮箱已注册")\n    new_user = User(email=user.email, hashed_password=hash_pw(user.password))\n    db.add(new_user)\n    await db.commit()\n    bg.add_task(send_verification_email, user.email)\n    return {"message": "注册成功"}\n\`\`\``,
  test_engineer: `## 测试报告\n\n| # | 用例 | 状态 |\n|---|------|------|\n| 1 | 正常注册流程 | ✅ PASSED |\n| 2 | 重复邮箱注册 | ✅ PASSED |\n| 3 | 无效邮箱格式 | ✅ PASSED |\n| 4 | 密码强度验证 | ✅ PASSED |\n| 5 | 登录流程 | ✅ PASSED |\n\n**结果: 5/5 通过, 覆盖率 92%**`,
  security_auditor: `## 安全审计报告\n\n| 检查项 | 状态 | 说明 |\n|--------|------|------|\n| 密码存储 | ✅ 安全 | 使用 bcrypt 哈希 |\n| SQL 注入 | ✅ 安全 | ORM 参数化查询 |\n| JWT 配置 | ⚠️ 建议 | 建议设置过期时间 |\n| 速率限制 | ⚠️ 建议 | 建议添加登录频率限制 |\n\n**总结: 未发现严重问题**`,
  code_reviewer: `## 代码审查\n\n### 总评: 👍 LGTM\n\n代码质量良好，建议合并。`,
  frontend_dev: `## 前端实现\n\n\`\`\`tsx\nexport function RegisterForm() {\n  return (\n    <form onSubmit={handleSubmit}>\n      <input placeholder="邮箱" type="email" />\n      <input placeholder="密码" type="password" />\n      <button>注册</button>\n    </form>\n  )\n}\n\`\`\``,
}

// ============ 主组件 ============

export default function TeamDevPage() {
  const [status, setStatus] = useState<TeamStatus>('idle')
  const [plan, setPlan] = useState<TaskPlan | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputText, setInputText] = useState('')
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const isExecuting = status === 'planning' || status === 'executing'

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const addMessage = (role: Message['role'], content: string, sender?: string) => {
    setMessages(prev => [...prev, {
      id: crypto.randomUUID(),
      role,
      content,
      sender,
      timestamp: Date.now(),
    }])
  }

  const updateTaskStatus = (taskId: string, newStatus: SubTaskStatus, output?: string, durationMs?: number) => {
    setPlan(prev => {
      if (!prev) return prev
      return {
        ...prev,
        subtasks: prev.subtasks.map(st =>
          st.id === taskId ? { ...st, status: newStatus, output, durationMs } : st
        ),
      }
    })
  }

  const handleSend = async () => {
    const text = inputText.trim()
    if (!text || isExecuting) return

    setInputText('')
    addMessage('user', text)

    // 阶段 1: Leader 分解
    setStatus('planning')
    await sleep(800)

    const taskPlan = decomposeTask(text)
    setPlan(taskPlan)
    addMessage('leader', taskPlan.summary, '🎯 Leader')

    // 阶段 2: 执行
    setStatus('executing')
    await sleep(500)

    await executeTasksInOrder(taskPlan.subtasks)

    setStatus('completed')
    addMessage('system', `✅ 所有 ${taskPlan.subtasks.length} 个任务已完成`)
  }

  const executeTasksInOrder = async (subtasks: SubTask[]) => {
    const completed = new Set<string>()

    while (completed.size < subtasks.length) {
      // 找可执行的任务
      const ready = subtasks.filter(st =>
        !completed.has(st.id) &&
        st.dependsOn.every(dep => completed.has(dep))
      )

      if (ready.length === 0) break

      // 并行执行
      await Promise.all(ready.map(async (task) => {
        updateTaskStatus(task.id, 'running')
        const delay = 1500 + Math.random() * 1500
        await sleep(delay)

        const output = MOCK_OUTPUTS[task.role] || `[${task.title}] 已完成`
        updateTaskStatus(task.id, 'completed', output, delay)
        completed.add(task.id)

        addMessage('agent', output, `${task.roleIcon} ${task.roleLabel} (${task.model})`)
      }))
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* 左侧：任务面板 */}
      <div className="w-72 border-r border-gray-200 flex flex-col bg-white">
        {/* 标题 */}
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Target size={16} className="text-blue-500" />
            <h2 className="text-sm font-bold text-gray-800">团队开发</h2>
          </div>
          {plan && (
            <p className="text-xs text-gray-400 mt-1">
              {plan.subtasks.filter(t => t.status === 'completed').length}/{plan.subtasks.length} 完成
            </p>
          )}
        </div>

        {/* Leader 状态 */}
        <div className="px-4 py-3 border-b border-gray-50 bg-blue-50/30">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
            <span>🎯</span>
            <span>Leader</span>
          </div>
          <p className={`text-xs mt-1 ${status === 'planning' ? 'text-amber-600' : 'text-gray-400'}`}>
            {status === 'idle' && '等待指令...'}
            {status === 'planning' && '正在拆解任务...'}
            {status === 'executing' && `执行中 (${plan?.subtasks.filter(t => t.status === 'completed').length}/${plan?.subtasks.length})`}
            {status === 'completed' && '✅ 全部完成'}
            {status === 'error' && '❌ 出错'}
          </p>
        </div>

        {/* 子任务列表 */}
        <div className="flex-1 overflow-y-auto">
          {plan ? (
            <div className="py-2">
              {plan.subtasks.map(task => (
                <div
                  key={task.id}
                  onClick={() => setSelectedTaskId(task.id === selectedTaskId ? null : task.id)}
                  className={`mx-2 mb-1 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
                    selectedTaskId === task.id
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <TaskStatusIcon status={task.status} />
                    <span className="text-xs font-medium text-gray-700 truncate flex-1">
                      {task.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1.5 ml-5">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ background: task.roleColor }}
                    />
                    <span className="text-[10px] text-gray-400">
                      {task.roleIcon} {task.roleLabel}
                    </span>
                    <span className="text-[10px] text-gray-300 font-mono">
                      {task.model}
                    </span>
                  </div>
                  {task.status === 'running' && (
                    <div className="ml-5 mt-1.5 h-1 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-400 rounded-full animate-pulse" style={{ width: '60%' }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-300">
              <Zap size={32} className="mb-2" />
              <p className="text-xs">发送指令开始</p>
            </div>
          )}
        </div>
      </div>

      {/* 右侧：对话区 */}
      <div className="flex-1 flex flex-col overflow-hidden bg-gray-50/30">
        {/* 消息区 */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <Bot size={40} className="mb-3 text-gray-300" />
              <p className="text-sm">输入开发需求，Leader 会自动分解并分配给团队</p>
              <p className="text-xs mt-1 text-gray-300">
                例如: "开发一个用户注册功能，要有邮箱验证"
              </p>
            </div>
          ) : (
            messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div className="px-6 py-4 border-t border-gray-200 bg-white">
          <div className="flex gap-3">
            <input
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="对 Leader 说话..."
              disabled={isExecuting}
              className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
            />
            <button
              onClick={handleSend}
              disabled={isExecuting || !inputText.trim()}
              className="px-4 py-2.5 bg-blue-500 text-white rounded-xl text-sm font-medium hover:bg-blue-600 disabled:bg-gray-200 disabled:text-gray-400 transition-colors flex items-center gap-1.5"
            >
              {isExecuting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              {isExecuting ? '执行中' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============ 子组件 ============

function TaskStatusIcon({ status }: { status: SubTaskStatus }) {
  switch (status) {
    case 'completed': return <CheckCircle2 size={14} className="text-green-500 shrink-0" />
    case 'running': return <Loader2 size={14} className="text-blue-500 animate-spin shrink-0" />
    case 'failed': return <XCircle size={14} className="text-red-500 shrink-0" />
    default: return <Clock size={14} className="text-gray-300 shrink-0" />
  }
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`mb-4 max-w-[85%] ${isUser ? 'ml-auto' : ''}`}>
      {message.sender && (
        <p className="text-[10px] text-gray-400 mb-1 px-1">
          {message.sender}
        </p>
      )}
      <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
        isUser
          ? 'bg-blue-500 text-white rounded-br-md'
          : message.role === 'leader'
          ? 'bg-white border border-gray-200 text-gray-700 rounded-bl-md'
          : message.role === 'system'
          ? 'bg-gray-100 text-gray-600 text-center text-xs rounded-lg'
          : 'bg-white border border-gray-100 text-gray-700 rounded-bl-md shadow-sm'
      }`}>
        {message.content}
      </div>
    </div>
  )
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
