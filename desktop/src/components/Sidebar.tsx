import { useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  Clock,
  Users,
  FolderOpen,
  MessageSquare,
  Settings,
  Star,
  Trash2
} from 'lucide-react'
import { useAppStore, Session } from '../store'

export default function Sidebar() {
  const navigate = useNavigate()
  const {
    sessions,
    currentSessionId,
    createSession,
    deleteSession,
    setCurrentSession
  } = useAppStore()

  const handleNewSession = () => {
    const id = createSession()
    navigate(`/chat/${id}`)
  }

  const handleSelectSession = (session: Session) => {
    setCurrentSession(session.id)
    navigate(`/chat/${session.id}`)
  }

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    deleteSession(id)
    if (currentSessionId === id) {
      navigate('/')
    }
  }

  const handleGoHome = () => {
    navigate('/')
  }

  const handleGoSettings = () => {
    navigate('/settings')
  }

  // 按 Agent 类型分组的团队列表
  const teamAgents = [
    { id: 'code_reviewer', name: '代码审查', icon: '🔍' },
    { id: 'architect', name: '架构师', icon: '🏗️' },
    { id: 'python_developer', name: 'Python 开发', icon: '🐍' },
    { id: 'bug_fixer', name: 'Bug 修复', icon: '🐛' },
    { id: 'agentic_rag', name: 'RAG 知识库', icon: '📚' }
  ]

  return (
    <aside className="w-60 h-full bg-sidebar-bg border-r border-gray-200 flex flex-col select-none">
      {/* 顶部操作区 */}
      <div className="p-3 space-y-1">
        {/* 新会话按钮 */}
        <button
          onClick={handleNewSession}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg hover:bg-sidebar-hover transition-colors"
        >
          <Plus size={16} />
          <span>新会话</span>
        </button>

        {/* 搜索 */}
        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg hover:bg-sidebar-hover transition-colors">
          <Search size={16} />
          <span>搜索</span>
        </button>

        {/* 定时任务 */}
        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg hover:bg-sidebar-hover transition-colors">
          <Clock size={16} />
          <span>定时任务</span>
        </button>
      </div>

      {/* 分割线 */}
      <div className="mx-3 border-t border-gray-200" />

      {/* 团队 Agent 列表 */}
      <div className="px-3 pt-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-400 font-medium uppercase">团队</span>
          <button className="text-gray-400 hover:text-gray-600">
            <Plus size={14} />
          </button>
        </div>
        <div className="space-y-0.5">
          {teamAgents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => {
                const id = createSession(agent.id)
                navigate(`/chat/${id}`)
              }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 rounded-lg hover:bg-sidebar-hover transition-colors"
            >
              <span className="text-base">{agent.icon}</span>
              <span className="truncate">{agent.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 分割线 */}
      <div className="mx-3 mt-3 border-t border-gray-200" />

      {/* 项目 */}
      <div className="px-3 pt-3">
        <span className="text-xs text-gray-400 font-medium uppercase">项目</span>
        <div className="mt-1 space-y-0.5">
          <button className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 rounded-lg hover:bg-sidebar-hover transition-colors">
            <FolderOpen size={14} />
            <span className="truncate">当前项目</span>
          </button>
        </div>
      </div>

      {/* 分割线 */}
      <div className="mx-3 mt-3 border-t border-gray-200" />

      {/* 对话历史 */}
      <div className="px-3 pt-3 flex-1 overflow-y-auto">
        <span className="text-xs text-gray-400 font-medium uppercase">对话</span>
        <div className="mt-1 space-y-0.5">
          {sessions.length === 0 ? (
            <p className="text-xs text-gray-400 px-3 py-2">暂无对话记录</p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => handleSelectSession(session)}
                className={`group w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg cursor-pointer transition-colors ${
                  currentSessionId === session.id
                    ? 'bg-sidebar-active text-gray-900'
                    : 'text-gray-600 hover:bg-sidebar-hover'
                }`}
              >
                <MessageSquare size={14} className="shrink-0" />
                <span className="truncate flex-1 text-left">{session.title}</span>
                <button
                  onClick={(e) => handleDeleteSession(e, session.id)}
                  className="opacity-0 group-hover:opacity-100 shrink-0 text-gray-400 hover:text-red-500 transition-all"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 底部操作 */}
      <div className="p-3 border-t border-gray-200 space-y-0.5">
        <button
          onClick={handleGoHome}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 rounded-lg hover:bg-sidebar-hover transition-colors"
        >
          <Star size={16} />
          <span>助手广场</span>
        </button>
        <button
          onClick={handleGoSettings}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 rounded-lg hover:bg-sidebar-hover transition-colors"
        >
          <Settings size={16} />
          <span>设置</span>
        </button>
      </div>
    </aside>
  )
}
