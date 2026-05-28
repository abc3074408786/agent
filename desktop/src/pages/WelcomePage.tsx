import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store'
import { Send, Plus, ChevronDown, MessageSquare, Star, Settings } from 'lucide-react'

// Agent 标签栏数据
const agentTabs = [
  { id: 'default', name: 'Agent', icon: '⊙', active: true },
  { id: 'claude', name: 'Claude', icon: '🌸', active: false },
  { id: 'gemini', name: 'Gemini', icon: '✦', active: false },
  { id: 'codex', name: 'Codex', icon: '⊙', active: false },
  { id: 'rag', name: 'RAG', icon: '📚', active: false },
]

// 助手卡片数据
const assistants = [
  { id: 'cowork', name: 'Cowork', description: '具有文件操作、文档处理和多...', icon: '⚡' },
  { id: 'word_assistant', name: 'Word 文档助手', description: '使用 officecli 创建、编辑和分...', icon: '📄' },
  { id: 'star_office', name: 'Star Office 助手', description: '用于在 Aion 浏览中安装、连...', icon: '🏢' },
  { id: 'moltbook', name: 'moltbook', description: 'AI 代理的社交网络、发帖、评...', icon: '📱' },
  { id: 'story_role', name: '故事角色扮演', description: '沉浸式故事角色扮演、三种开...', icon: '🎭' },
  { id: 'academic', name: '学术论文助手', description: '创建正式结构的学术论文、研...', icon: '🎓' },
  { id: 'ppt_assistant', name: 'PPT 演示助手', description: '使用 officecli 创建、编辑和分...', icon: '📊' },
  { id: 'morph_ppt', name: 'Morph PPT', description: '使用 officecli 创建专业的 Mo...', icon: '✨' },
  { id: 'openclaw', name: 'OpenClaw 部署专家', description: 'OpenClaw 安装、配置、部署...', icon: '🐾' },
]

export default function WelcomePage() {
  const navigate = useNavigate()
  const { createSession, setPendingSessionId } = useAppStore()
  const [activeAgent, setActiveAgent] = useState('default')
  const [inputText, setInputText] = useState('')
  const [selectedModel, setSelectedModel] = useState('mimo-v2-pro')

  const handleSelectAssistant = (assistantId: string) => {
    const sessionId = createSession(assistantId)
    navigate(`/chat/${sessionId}`)
  }

  const handleSendMessage = () => {
    if (!inputText.trim()) return
    const sessionId = createSession(activeAgent !== 'default' ? activeAgent : undefined)
    useAppStore.getState().addMessage(sessionId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: inputText.trim(),
      timestamp: Date.now()
    })
    setPendingSessionId(sessionId)
    navigate(`/chat/${sessionId}`)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-white">
      {/* 主内容区 */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 pb-4">
        {/* 问候语 */}
        <h1 className="text-2xl font-bold text-gray-800 mb-8">Hi，今天有什么安排?</h1>

        {/* Agent 标签切换栏 */}
        <div className="flex items-center gap-1 mb-4 px-3 py-1.5 bg-gray-50 rounded-full border border-gray-200">
          {agentTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveAgent(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-full transition-all ${
                activeAgent === tab.id
                  ? 'bg-white text-gray-800 shadow-sm border border-gray-200 font-medium'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="text-sm">{tab.icon}</span>
              <span>{tab.name}</span>
            </button>
          ))}
          <button className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors">
            <Plus size={14} />
          </button>
        </div>

        {/* 输入框 */}
        <div className="w-full max-w-2xl mb-3">
          <div className="relative border border-gray-200 rounded-xl bg-white shadow-sm">
            {/* 文本输入 */}
            <div className="px-4 pt-3 pb-2">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Aion CLI，发消息、上传文件、打开文件夹或"
                rows={1}
                className="w-full resize-none outline-none text-sm text-gray-700 placeholder-gray-400 bg-transparent leading-6"
              />
            </div>

            {/* 底部工具栏 */}
            <div className="flex items-center justify-between px-3 pb-2.5">
              {/* 左侧：附件 */}
              <button className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-50 transition-colors">
                <Plus size={16} />
              </button>

              {/* 右侧：模型选择 + Agent选择 + 发送 */}
              <div className="flex items-center gap-2">
                {/* 模型选择器 */}
                <button className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-500 rounded-lg hover:bg-gray-50 border border-gray-200 transition-colors">
                  <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
                  <span>{selectedModel}</span>
                  <ChevronDown size={11} />
                </button>

                {/* Agent 选择器 */}
                <button className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-500 rounded-lg hover:bg-gray-50 border border-gray-200 transition-colors">
                  <span>⊙</span>
                  <span>默认</span>
                  <ChevronDown size={11} />
                </button>

                {/* 发送按钮 */}
                <button
                  onClick={handleSendMessage}
                  disabled={!inputText.trim()}
                  className={`p-2 rounded-lg transition-colors ${
                    inputText.trim()
                      ? 'bg-blue-500 text-white hover:bg-blue-600'
                      : 'bg-gray-100 text-gray-300'
                  }`}
                >
                  <Send size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* 在项目中工作 */}
          <div className="mt-2 px-1">
            <button className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors">
              <span className="w-3.5 h-3.5 border border-gray-300 rounded" />
              <span>在项目中工作</span>
              <ChevronDown size={10} />
            </button>
          </div>
        </div>

        {/* 助手卡片区域 */}
        <div className="w-full max-w-4xl mt-6">
          <p className="text-center text-sm text-gray-500 mb-4">选择一位助手开始任务</p>
          <div className="grid grid-cols-3 gap-3">
            {assistants.map((assistant) => (
              <button
                key={assistant.id}
                onClick={() => handleSelectAssistant(assistant.id)}
                className="flex items-start gap-3 p-4 rounded-xl border border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm transition-all text-left group"
              >
                <span className="text-2xl shrink-0 mt-0.5">{assistant.icon}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 group-hover:text-blue-600 transition-colors">
                    {assistant.name}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                    {assistant.description}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 底部导航栏 */}
      <div className="flex items-center justify-center gap-6 py-3 border-t border-gray-100">
        <button
          onClick={() => navigate('/')}
          className="p-2 text-gray-400 hover:text-blue-500 transition-colors"
          title="对话"
        >
          <MessageSquare size={20} />
        </button>
        <button
          className="p-2 text-gray-400 hover:text-blue-500 transition-colors"
          title="收藏"
        >
          <Star size={20} />
        </button>
        <button
          onClick={() => navigate('/settings')}
          className="p-2 text-gray-400 hover:text-blue-500 transition-colors"
          title="设置"
        >
          <Settings size={20} />
        </button>
      </div>
    </div>
  )
}
