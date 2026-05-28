import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface SubTask {
  id: string
  title: string
  description: string
  role: string
  role_icon: string
  role_label: string
  role_color: string
  model: string
  depends_on: string[]
  priority: number
  estimated_time: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

export interface TaskPlan {
  id: string
  user_request: string
  summary: string
  subtasks: SubTask[]
  created_at: number
}

export interface Message {
  id: string
  role: 'user' | 'leader' | 'agent' | 'system'
  content: string
  sender?: string
  timestamp: number
}

export interface LogEntry {
  message: string
  level: string
  timestamp: number
}

export const useTeamStore = defineStore('team', () => {
  // 状态
  const sessionId = ref<string | null>(null)
  const status = ref<string>('idle')
  const serverStatus = ref<string>('starting')
  const serverPort = ref(8080)
  const messages = ref<Message[]>([])
  const plan = ref<TaskPlan | null>(null)
  const logs = ref<LogEntry[]>([])
  const isConnected = ref(false)
  const isExecuting = ref(false)

  // WebSocket
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  // Computed
  const tasks = computed(() => plan.value?.subtasks || [])
  const completedCount = computed(() => tasks.value.filter(t => t.status === 'completed').length)
  const totalCount = computed(() => tasks.value.length)

  // Actions
  function connect() {
    // 先通过 HTTP 创建会话
    fetch(`http://localhost:${serverPort.value}/api/sessions`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        sessionId.value = data.session_id
        serverStatus.value = 'running'
        connectWebSocket()
      })
      .catch(() => {
        // 服务器还没启动，延迟重试
        console.log('[WS] Server not ready, retrying in 2s...')
        reconnectTimer = setTimeout(() => connect(), 2000)
      })
  }

  function connectWebSocket() {
    if (!sessionId.value) return

    const url = `ws://localhost:${serverPort.value}/ws/${sessionId.value}`
    ws = new WebSocket(url)

    ws.onopen = () => {
      isConnected.value = true
      console.log('WebSocket connected')
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        handleEvent(event)
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    ws.onclose = () => {
      isConnected.value = false
      ws = null
      // 自动重连
      reconnectTimer = setTimeout(() => connectWebSocket(), 3000)
    }

    ws.onerror = () => {
      isConnected.value = false
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
  }

  function handleEvent(event: any) {
    switch (event.type) {
      case 'connected':
        if (event.plan) plan.value = event.plan
        if (event.messages) {
          // Restore messages
        }
        break

      case 'status':
        status.value = event.status
        if (event.status === 'completed' || event.status === 'error') {
          isExecuting.value = false
        }
        break

      case 'plan':
        plan.value = event.plan
        addMessage('leader', event.plan.summary, '🎯 Leader')
        break

      case 'task_started':
        updateTaskStatus(event.task_id, 'running')
        break

      case 'task_progress':
        // 可以用来显示进度动画
        break

      case 'task_completed':
        updateTaskStatus(event.task_id, 'completed')
        if (event.output) {
          const roleInfo = getRoleInfo(event.role)
          addMessage('agent', event.output, `${roleInfo.icon} ${roleInfo.label} (${event.model})`)
        }
        break

      case 'task_failed':
        updateTaskStatus(event.task_id, 'failed')
        addMessage('system', `❌ ${event.task_title}: ${event.message}`, '系统')
        break

      case 'all_completed':
        status.value = 'completed'
        isExecuting.value = false
        addMessage('system', event.message, '🎯 Leader')
        break

      case 'error':
        status.value = 'error'
        isExecuting.value = false
        addMessage('system', `❌ ${event.message}`, '系统')
        break

      case 'cancelled':
        status.value = 'idle'
        isExecuting.value = false
        addMessage('system', `⛔ ${event.message}`, '系统')
        break
    }
  }

  function sendMessage(content: string) {
    if (!content.trim() || isExecuting.value) return

    // 添加用户消息
    addMessage('user', content)

    // 发送到服务器
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'message', content }))
      isExecuting.value = true
      status.value = 'planning'
    }
  }

  function cancelExecution() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel' }))
    }
  }

  function addMessage(role: Message['role'], content: string, sender?: string) {
    messages.value.push({
      id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      role,
      content,
      sender,
      timestamp: Date.now(),
    })
  }

  function updateTaskStatus(taskId: string, newStatus: SubTask['status']) {
    if (!plan.value) return
    const task = plan.value.subtasks.find(t => t.id === taskId)
    if (task) {
      task.status = newStatus
    }
  }

  function addLog(message: string, level: string = 'info') {
    logs.value.push({ message, level, timestamp: Date.now() })
    if (logs.value.length > 200) logs.value.shift()
  }

  function getRoleInfo(role: string) {
    const map: Record<string, { icon: string; label: string }> = {
      python_dev: { icon: '🐍', label: 'Python 开发' },
      frontend_dev: { icon: '⚛️', label: '前端开发' },
      backend_dev: { icon: '🔧', label: '后端开发' },
      test_engineer: { icon: '🧪', label: '测试工程师' },
      security_auditor: { icon: '🛡️', label: '安全审计' },
      architect: { icon: '🏗️', label: '架构师' },
      devops: { icon: '🚀', label: 'DevOps' },
      database_expert: { icon: '🗄️', label: '数据库专家' },
      code_reviewer: { icon: '👁️', label: '代码审查' },
    }
    return map[role] || { icon: '🤖', label: 'Agent' }
  }

  return {
    // State
    sessionId,
    status,
    serverStatus,
    serverPort,
    messages,
    plan,
    logs,
    isConnected,
    isExecuting,
    // Computed
    tasks,
    completedCount,
    totalCount,
    // Actions
    connect,
    disconnect,
    sendMessage,
    cancelExecution,
    addMessage,
    addLog,
    getRoleInfo,
  }
})
