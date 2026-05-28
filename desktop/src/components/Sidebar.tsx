import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  Plus, Search, Clock, ChevronDown, ChevronRight,
  MessageSquare, Settings, Trash2, FolderOpen, ListFilter,
  Users
} from 'lucide-react'
import { useAppStore, Session } from '../store'
import CreateTeamModal from './CreateTeamModal'

interface ProjectItem {
  id: string
  name: string
  icon: string
  conversations: { id: string; title: string; icon: string }[]
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const {
    sessions,
    currentSessionId,
    createSession,
    deleteSession,
    setCurrentSession
  } = useAppStore()

  const [showCreateTeam, setShowCreateTeam] = useState(false)
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set(['1', '2']))

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

  // 团队数据（从 store 读取）
  const storeTeams = useAppStore((state) => state.teams)
  const teams = storeTeams.length > 0
    ? storeTeams.map(t => ({ id: t.id, name: t.name, icon: t.leader.icon }))
    : [
        { id: 'sales_agent', name: 'sales_agent', icon: '👤' },
        { id: 'web', name: '网页', icon: '👤' },
        { id: 'agentic_rag', name: 'agentic_rag', icon: '👤' },
      ]

  // 项目数据
  const projects: ProjectItem[] = [
    {
      id: '1',
      name: 'data_cleaner',
      icon: '📁',
      conversations: [
        { id: 'c1', title: '这是什么项目', icon: '⊙' },
      ]
    },
    {
      id: '2',
      name: 'rag_app',
      icon: '📁',
      conversations: [
        { id: 'c2', title: '你好', icon: '🌸' },
      ]
    }
  ]

  const toggleProject = (id: string) => {
    const next = new Set(expandedProjects)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpandedProjects(next)
  }

  // 获取对话图标（根据 agent 类型）
  const getSessionIcon = (session: Session) => {
    if (session.agentType === 'agentic_rag') return '📚'
    if (session.agentType === 'code_reviewer') return '🔍'
    if (session.agentType === 'python_developer') return '🐍'
    return '⊙'
  }

  return (
    <aside className="w-[220px] h-full bg-white border-r border-gray-200 flex flex-col select-none">
      {/* 顶部操作区 */}
      <div className="px-3 pt-3 pb-2 space-y-0.5">
        {/* 新会话 + 排序按钮 */}
        <div className="flex items-center gap-1">
          <button
            onClick={handleNewSession}
            className="flex-1 flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <Plus size={15} className="text-gray-500" />
            <span>新会话</span>
          </button>
          <button className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors">
            <ListFilter size={15} />
          </button>
        </div>

        {/* 搜索 */}
        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors">
          <Search size={15} className="text-gray-400" />
          <span>搜索</span>
        </button>

        {/* 定时任务 */}
        <button
          onClick={() => navigate('/automations')}
          className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
            location.pathname === '/automations'
              ? 'bg-gray-100 text-gray-900'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          <Clock size={15} className="text-gray-400" />
          <span>定时任务</span>
        </button>
      </div>

      {/* 团队分组 */}
      <div className="px-3 pt-2">
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-xs text-gray-400 font-medium">团队</span>
          <button
            onClick={() => setShowCreateTeam(true)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <Plus size={13} />
          </button>
        </div>
        <div className="space-y-0.5">
          {teams.map((team) => (
            <button
              key={team.id}
              onClick={() => {
                const id = createSession(team.id)
                navigate(`/chat/${id}`)
              }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <Users size={14} className="text-gray-400" />
              <span className="truncate">{team.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 项目分组 */}
      <div className="px-3 pt-3">
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-xs text-gray-400 font-medium">项目</span>
        </div>
        <div className="space-y-0.5">
          {projects.map((project) => (
            <div key={project.id}>
              {/* 项目行 */}
              <button
                onClick={() => toggleProject(project.id)}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
              >
                {expandedProjects.has(project.id) ? (
                  <ChevronDown size={12} className="text-gray-400" />
                ) : (
                  <ChevronRight size={12} className="text-gray-400" />
                )}
                <FolderOpen size={14} className="text-gray-400" />
                <span className="truncate">{project.name}</span>
              </button>
              {/* 项目下的对话 */}
              {expandedProjects.has(project.id) && (
                <div className="ml-4 space-y-0.5">
                  {project.conversations.map((conv) => (
                    <button
                      key={conv.id}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-500 rounded-lg hover:bg-gray-100 transition-colors"
                    >
                      <span className="text-xs">{conv.icon}</span>
                      <span className="truncate">{conv.title}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 对话分组 */}
      <div className="px-3 pt-3 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-xs text-gray-400 font-medium">对话</span>
        </div>
        <div className="space-y-0.5">
          {sessions.length === 0 ? (
            <p className="text-xs text-gray-400 px-3 py-2">暂无对话记录</p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => handleSelectSession(session)}
                className={`group w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg cursor-pointer transition-colors ${
                  currentSessionId === session.id
                    ? 'bg-gray-100 text-gray-900'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <span className="text-xs shrink-0">{getSessionIcon(session)}</span>
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

      {/* 底部：设置 */}
      <div className="px-3 py-3 border-t border-gray-100">
        <button
          onClick={() => navigate('/settings')}
          className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
            location.pathname === '/settings'
              ? 'bg-gray-100 text-gray-900'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          <Settings size={15} className="text-gray-400" />
          <span>设置</span>
        </button>
      </div>

      {/* 创建团队弹窗 */}
      {showCreateTeam && (
        <CreateTeamModal
          onClose={() => setShowCreateTeam(false)}
          onCreate={(teamData) => {
            useAppStore.getState().addTeam({
              name: teamData.name,
              description: teamData.description,
              leader: teamData.leader,
              members: teamData.members,
              project: teamData.project
            })
            setShowCreateTeam(false)
          }}
        />
      )}
    </aside>
  )
}
