import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  Plus, Search, Clock, ChevronDown, ChevronRight,
  MessageSquare, Settings, Trash2, FolderOpen, Users,
  PanelLeftClose, PanelLeftOpen, Bot, Zap
} from 'lucide-react'
import { useAppStore, Session } from '../store'
import CreateTeamModal from './CreateTeamModal'

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const {
    sessions, currentSessionId, createSession, deleteSession, setCurrentSession,
    settings, toggleSidebar
  } = useAppStore()

  const [showCreateTeam, setShowCreateTeam] = useState(false)
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set(['1']))

  const collapsed = settings.sidebarCollapsed

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
    if (currentSessionId === id) navigate('/')
  }

  const storeTeams = useAppStore((state) => state.teams)
  const teams = storeTeams.length > 0
    ? storeTeams.map(t => ({ id: t.id, name: t.name, icon: '👥' }))
    : [{ id: 'default_team', name: '标准开发组', icon: '👥' }]

  const getSessionIcon = (session: Session) => {
    if (session.agentType === 'code_reviewer') return '🔍'
    if (session.agentType === 'python_developer') return '🐍'
    if (session.agentType === 'full_stack') return '🚀'
    if (session.agentType === 'architect') return '🏗️'
    return '⊙'
  }

  // Collapsed mode
  if (collapsed) {
    return (
      <aside
        className="w-14 h-full flex flex-col items-center py-3 border-r border-border transition-all"
        style={{ background: 'var(--sidebar-bg)' }}
      >
        <button
          onClick={toggleSidebar}
          className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary mb-3 transition-colors"
          title="展开侧边栏"
        >
          <PanelLeftOpen size={16} />
        </button>

        <button
          onClick={handleNewSession}
          className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary mb-1 transition-colors"
          title="新会话"
        >
          <Plus size={16} />
        </button>

        <button
          onClick={() => navigate('/agents')}
          className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary mb-1 transition-colors"
          title="多 Agent"
        >
          <Bot size={16} />
        </button>

        <button
          onClick={() => navigate('/team')}
          className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary mb-1 transition-colors"
          title="团队开发"
        >
          <Users size={16} />
        </button>

        <button
          onClick={() => navigate('/automations')}
          className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary mb-1 transition-colors"
          title="定时任务"
        >
          <Clock size={16} />
        </button>

        <div className="flex-1" />

        <button
          onClick={() => navigate('/settings')}
          className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors"
          title="设置"
        >
          <Settings size={16} />
        </button>
      </aside>
    )
  }

  // Expanded mode
  return (
    <aside
      className="h-full flex flex-col select-none border-r border-border transition-all"
      style={{ width: `${settings.sidebarWidth}px`, background: 'var(--sidebar-bg)' }}
    >
      {/* Top actions */}
      <div className="px-3 pt-3 pb-2 space-y-0.5">
        <div className="flex items-center gap-1">
          <button
            onClick={handleNewSession}
            className="flex-1 flex items-center gap-2 px-3 py-2 text-sm text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors"
          >
            <Plus size={15} className="text-text-secondary" />
            <span>新会话</span>
          </button>
          <button
            onClick={toggleSidebar}
            className="p-2 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors"
            title="折叠侧边栏"
          >
            <PanelLeftClose size={15} />
          </button>
        </div>

        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-text-secondary rounded-lg hover:bg-surface-tertiary transition-colors">
          <Search size={15} className="text-text-tertiary" />
          <span>搜索</span>
          <kbd className="ml-auto text-[10px] text-text-tertiary bg-surface-tertiary px-1.5 py-0.5 rounded border border-border">⌘K</kbd>
        </button>

        <button
          onClick={() => navigate('/automations')}
          className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
            location.pathname === '/automations'
              ? 'bg-surface-tertiary text-text-primary font-medium'
              : 'text-text-secondary hover:bg-surface-tertiary'
          }`}
        >
          <Clock size={15} className="text-text-tertiary" />
          <span>定时任务</span>
        </button>
      </div>

      {/* Teams */}
      <div className="px-3 pt-2">
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-[10px] text-text-tertiary font-semibold uppercase tracking-wider">团队</span>
          <button
            onClick={() => setShowCreateTeam(true)}
            className="text-text-tertiary hover:text-text-primary transition-colors"
          >
            <Plus size={12} />
          </button>
        </div>
        <div className="space-y-0.5">
          {teams.map((team) => (
            <button
              key={team.id}
              onClick={() => navigate('/team')}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                location.pathname === '/team'
                  ? 'bg-surface-tertiary text-text-primary'
                  : 'text-text-secondary hover:bg-surface-tertiary'
              }`}
            >
              <Users size={14} className="text-text-tertiary" />
              <span className="truncate">{team.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Sessions */}
      <div className="px-3 pt-3 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-1 px-1">
          <span className="text-[10px] text-text-tertiary font-semibold uppercase tracking-wider">对话</span>
        </div>
        <div className="space-y-0.5">
          {sessions.length === 0 ? (
            <p className="text-xs text-text-tertiary px-3 py-2">暂无对话记录</p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => handleSelectSession(session)}
                className={`group w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg cursor-pointer transition-colors ${
                  currentSessionId === session.id
                    ? 'bg-surface-tertiary text-text-primary font-medium'
                    : 'text-text-secondary hover:bg-surface-tertiary'
                }`}
              >
                <span className="text-xs shrink-0">{getSessionIcon(session)}</span>
                <span className="truncate flex-1 text-left">{session.title}</span>
                <button
                  onClick={(e) => handleDeleteSession(e, session.id)}
                  className="opacity-0 group-hover:opacity-100 shrink-0 text-text-tertiary hover:text-accent-red transition-all"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Bottom */}
      <div className="px-3 py-3 border-t border-border">
        <button
          onClick={() => navigate('/settings')}
          className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
            location.pathname === '/settings'
              ? 'bg-surface-tertiary text-text-primary font-medium'
              : 'text-text-secondary hover:bg-surface-tertiary'
          }`}
        >
          <Settings size={15} className="text-text-tertiary" />
          <span>设置</span>
        </button>
      </div>

      {/* Create team modal */}
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
