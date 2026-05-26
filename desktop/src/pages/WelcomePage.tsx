import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store'
import InputBox from '../components/InputBox'

// 助手卡片数据
const assistants = [
  {
    id: 'code_reviewer',
    name: '代码审查',
    description: '审查代码质量、安全性、性能问题',
    icon: '🔍',
    color: 'bg-blue-50 border-blue-200'
  },
  {
    id: 'architect',
    name: '架构师',
    description: '系统设计、技术选型、架构优化',
    icon: '🏗️',
    color: 'bg-purple-50 border-purple-200'
  },
  {
    id: 'python_developer',
    name: 'Python 开发',
    description: 'Python 最佳实践、开发与调试',
    icon: '🐍',
    color: 'bg-green-50 border-green-200'
  },
  {
    id: 'bug_fixer',
    name: 'Bug 修复',
    description: 'Bug 定位、修复与回归测试',
    icon: '🐛',
    color: 'bg-red-50 border-red-200'
  },
  {
    id: 'full_stack',
    name: '全栈开发',
    description: '前端 + 后端 + DevOps 全栈能力',
    icon: '⚡',
    color: 'bg-yellow-50 border-yellow-200'
  },
  {
    id: 'agentic_rag',
    name: 'RAG 知识库',
    description: '基于知识库检索增强的智能问答',
    icon: '📚',
    color: 'bg-indigo-50 border-indigo-200'
  },
  {
    id: 'security_auditor',
    name: '安全审计',
    description: '安全漏洞扫描和修复建议',
    icon: '🛡️',
    color: 'bg-orange-50 border-orange-200'
  },
  {
    id: 'devops_agent',
    name: 'DevOps',
    description: 'CI/CD、容器化、自动化部署',
    icon: '🚀',
    color: 'bg-cyan-50 border-cyan-200'
  },
  {
    id: 'data_analyst',
    name: '数据分析',
    description: '数据探索、建模和可视化',
    icon: '📊',
    color: 'bg-pink-50 border-pink-200'
  }
]

export default function WelcomePage() {
  const navigate = useNavigate()
  const { createSession, setPendingSessionId } = useAppStore()

  const handleSelectAssistant = (agentId: string) => {
    const sessionId = createSession(agentId)
    navigate(`/chat/${sessionId}`)
  }

  const handleSendMessage = (message: string) => {
    const sessionId = createSession()
    // 添加用户消息
    useAppStore.getState().addMessage(sessionId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now()
    })
    // 标记为待处理，ChatPage 加载后自动触发 AI 回复
    setPendingSessionId(sessionId)
    navigate(`/chat/${sessionId}`)
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* 欢迎语 */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 pb-8">
        <h1 className="text-2xl font-bold text-gray-800 mb-10">Hi，今天有什么安排?</h1>

        {/* 输入框 */}
        <div className="w-full max-w-2xl mb-10">
          <InputBox onSend={handleSendMessage} placeholder="发消息、上传文件、打开文件夹或" />
        </div>

        {/* 助手卡片 */}
        <div className="w-full max-w-4xl">
          <p className="text-center text-sm text-gray-500 mb-4">选择一位助手开始任务</p>
          <div className="grid grid-cols-3 gap-3">
            {assistants.map((assistant) => (
              <button
                key={assistant.id}
                onClick={() => handleSelectAssistant(assistant.id)}
                className={`flex items-start gap-3 p-4 rounded-xl border ${assistant.color} hover:shadow-md transition-all text-left group`}
              >
                <span className="text-2xl shrink-0 mt-0.5">{assistant.icon}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 group-hover:text-primary-600 transition-colors">
                    {assistant.name}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                    {assistant.description}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
