import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// ============================================
// Types
// ============================================

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: number
  model?: string
  toolCalls?: ToolCall[]
}

export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown>
  status: 'running' | 'completed' | 'failed'
  result?: string
  durationMs?: number
  startedAt: number
}

export interface Artifact {
  id: string
  filename: string
  language: string
  content: string
  createdAt: number
}

export interface Session {
  id: string
  title: string
  messages: Message[]
  model: string
  agentType?: string
  artifacts: Artifact[]
  createdAt: number
  updatedAt: number
}

// Project types
export interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children?: FileTreeNode[]
  expanded?: boolean
}

export interface Project {
  id: string
  name: string
  path: string // absolute filesystem path
  sessions: string[] // session IDs associated with this project
  createdAt: number
}

export interface AgentPreset {
  id: string
  name: string
  description: string
  icon: string
  color: string
}

export interface TeamMember {
  agentId: string
  agentName: string
  icon: string
  model: string
  role: 'leader' | 'member'
}

export interface Team {
  id: string
  name: string
  description: string
  leader: TeamMember
  members: TeamMember[]
  project?: string
  createdAt: number
}

export interface Settings {
  // LLM mode
  llmMode: 'user_key' | 'proxy'
  openaiKey: string
  anthropicKey: string
  proxyUrl: string
  proxyKey: string
  // Agent
  agentMode: 'local' | 'remote'
  agentLocalPort: number
  agentRemoteUrl: string
  // RAG
  ragUrl: string
  ragKey: string
  // Model
  defaultModel: string
  // Theme
  theme: 'light' | 'dark' | 'system'
  // Sidebar
  sidebarCollapsed: boolean
  sidebarWidth: number
  // Artifacts
  artifactsPanelOpen: boolean
}

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  title: string
  description?: string
  duration?: number
}

export type ConnectionStatus = 'connected' | 'disconnected' | 'checking'

// Available models
export interface ModelOption {
  id: string
  name: string
  provider: 'openai' | 'anthropic' | 'custom'
  icon: string
}

// Fallback defaults (used when API is unreachable)
export const DEFAULT_MODELS: ModelOption[] = [
  { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai', icon: '●' },
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai', icon: '○' },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', provider: 'openai', icon: '●' },
  { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4', provider: 'anthropic', icon: '◈' },
  { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'anthropic', icon: '◆' },
  { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', provider: 'anthropic', icon: '◇' },
]

// Available agents
export interface AgentOption {
  id: string
  name: string
  description: string
  icon: string
}

// Fallback defaults (used when API is unreachable)
export const DEFAULT_AGENTS: AgentOption[] = [
  { id: 'default', name: '默认 Agent', description: '通用智能助手', icon: '⊙' },
  { id: 'code_reviewer', name: '代码审查', description: '代码审查 + 安全审计', icon: '🔍' },
  { id: 'python_developer', name: 'Python 开发', description: 'Python 开发 + 测试', icon: '🐍' },
  { id: 'full_stack', name: '全栈开发', description: '前端 + 后端 + DevOps', icon: '🚀' },
  { id: 'architect', name: '架构师', description: '系统设计 + 数据库', icon: '🏗️' },
  { id: 'bug_fixer', name: 'Bug 修复', description: '定位 + 修复 + 回归测试', icon: '🐛' },
  { id: 'security_auditor', name: '安全审计', description: '漏洞扫描 + 修复建议', icon: '🛡️' },
  { id: 'test_engineer', name: '测试工程师', description: '测试策略 + 自动化', icon: '🧪' },
]

// Re-export for backward compatibility - components use these
// They get overridden at runtime by fetchRemoteConfig()
export let AVAILABLE_MODELS: ModelOption[] = [...DEFAULT_MODELS]
export let AVAILABLE_AGENTS: AgentOption[] = [...DEFAULT_AGENTS]

// ============================================
// Store
// ============================================

interface AppState {
  // Sessions
  sessions: Session[]
  currentSessionId: string | null
  // Projects
  projects: Project[]
  currentProjectId: string | null
  projectFilesOpen: boolean
  fileTree: FileTreeNode[]
  // Teams
  teams: Team[]
  // Settings
  settings: Settings
  // Dynamic config (fetched from backend)
  remoteModels: ModelOption[]
  remoteAgents: AgentOption[]
  // Runtime (not persisted)
  agentRunning: boolean
  isGenerating: boolean
  abortController: AbortController | null
  pendingSessionId: string | null
  connectionStatus: ConnectionStatus
  toasts: Toast[]
  commandPaletteOpen: boolean
  // Actions: Sessions
  createSession: (agentType?: string) => string
  deleteSession: (id: string) => void
  setCurrentSession: (id: string) => void
  addMessage: (sessionId: string, message: Message) => void
  updateLastMessage: (sessionId: string, content: string) => void
  appendToLastMessage: (sessionId: string, chunk: string) => void
  addToolCallToLastMessage: (sessionId: string, toolCall: ToolCall) => void
  updateToolCall: (sessionId: string, toolCallId: string, update: Partial<ToolCall>) => void
  addArtifact: (sessionId: string, artifact: Artifact) => void
  // Actions: Settings
  updateSettings: (settings: Partial<Settings>) => void
  toggleSidebar: () => void
  toggleArtifactsPanel: () => void
  // Actions: Runtime
  setAgentRunning: (running: boolean) => void
  setIsGenerating: (generating: boolean) => void
  setAbortController: (controller: AbortController | null) => void
  setPendingSessionId: (id: string | null) => void
  setConnectionStatus: (status: ConnectionStatus) => void
  // Actions: Toast
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
  // Actions: Command Palette
  setCommandPaletteOpen: (open: boolean) => void
  // Actions: Teams
  addTeam: (team: Omit<Team, 'id' | 'createdAt'>) => string
  removeTeam: (id: string) => void
  updateTeam: (id: string, partial: Partial<Team>) => void
  // Actions: Projects
  addProject: (name: string, path: string) => string
  removeProject: (id: string) => void
  setCurrentProject: (id: string | null) => void
  toggleProjectFiles: () => void
  setFileTree: (tree: FileTreeNode[]) => void
  linkSessionToProject: (projectId: string, sessionId: string) => void
  // Actions: Dynamic config
  fetchRemoteConfig: () => Promise<void>
  getModels: () => ModelOption[]
  getAgents: () => AgentOption[]
}

const defaultSettings: Settings = {
  llmMode: 'user_key',
  openaiKey: '',
  anthropicKey: '',
  proxyUrl: '',
  proxyKey: '',
  agentMode: 'local',
  agentLocalPort: 8765,
  agentRemoteUrl: '',
  ragUrl: '',
  ragKey: '',
  defaultModel: 'gpt-4o',
  theme: 'dark',
  sidebarCollapsed: false,
  sidebarWidth: 240,
  artifactsPanelOpen: false,
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      projects: [],
      currentProjectId: null,
      projectFilesOpen: false,
      fileTree: [],
      teams: [],
      settings: defaultSettings,
      remoteModels: [],
      remoteAgents: [],
      agentRunning: false,
      isGenerating: false,
      abortController: null,
      pendingSessionId: null,
      connectionStatus: 'disconnected',
      toasts: [],
      commandPaletteOpen: false,

      createSession: (agentType?: string) => {
        const id = crypto.randomUUID()
        const session: Session = {
          id,
          title: '新对话',
          messages: [],
          model: get().settings.defaultModel,
          agentType,
          artifacts: [],
          createdAt: Date.now(),
          updatedAt: Date.now()
        }
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: id
        }))
        return id
      },

      deleteSession: (id: string) => {
        set((state) => ({
          sessions: state.sessions.filter((s) => s.id !== id),
          currentSessionId: state.currentSessionId === id ? null : state.currentSessionId
        }))
      },

      setCurrentSession: (id: string) => {
        set({ currentSessionId: id })
      },

      addMessage: (sessionId: string, message: Message) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s
            const updated = {
              ...s,
              messages: [...s.messages, message],
              updatedAt: Date.now()
            }
            if (message.role === 'user' && s.messages.length === 0) {
              updated.title = message.content.slice(0, 30)
            }
            return updated
          })
        }))
      },

      updateLastMessage: (sessionId: string, content: string) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s
            const messages = [...s.messages]
            if (messages.length > 0) {
              messages[messages.length - 1] = { ...messages[messages.length - 1], content }
            }
            return { ...s, messages, updatedAt: Date.now() }
          })
        }))
      },

      appendToLastMessage: (sessionId: string, chunk: string) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s
            const messages = [...s.messages]
            if (messages.length > 0) {
              const lastMsg = messages[messages.length - 1]
              messages[messages.length - 1] = { ...lastMsg, content: lastMsg.content + chunk }
            }
            return { ...s, messages, updatedAt: Date.now() }
          })
        }))
      },

      addToolCallToLastMessage: (sessionId: string, toolCall: ToolCall) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s
            const messages = [...s.messages]
            if (messages.length > 0) {
              const lastMsg = messages[messages.length - 1]
              const toolCalls = [...(lastMsg.toolCalls || []), toolCall]
              messages[messages.length - 1] = { ...lastMsg, toolCalls }
            }
            return { ...s, messages, updatedAt: Date.now() }
          })
        }))
      },

      updateToolCall: (sessionId: string, toolCallId: string, update: Partial<ToolCall>) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s
            const messages = [...s.messages]
            for (let i = messages.length - 1; i >= 0; i--) {
              const msg = messages[i]
              if (msg.toolCalls) {
                const idx = msg.toolCalls.findIndex((tc) => tc.id === toolCallId)
                if (idx !== -1) {
                  const toolCalls = [...msg.toolCalls]
                  toolCalls[idx] = { ...toolCalls[idx], ...update }
                  messages[i] = { ...msg, toolCalls }
                  break
                }
              }
            }
            return { ...s, messages, updatedAt: Date.now() }
          })
        }))
      },

      addArtifact: (sessionId: string, artifact: Artifact) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s
            return { ...s, artifacts: [...s.artifacts, artifact], updatedAt: Date.now() }
          })
        }))
      },

      updateSettings: (partial: Partial<Settings>) => {
        set((state) => ({
          settings: { ...state.settings, ...partial }
        }))
      },

      toggleSidebar: () => {
        set((state) => ({
          settings: { ...state.settings, sidebarCollapsed: !state.settings.sidebarCollapsed }
        }))
      },

      toggleArtifactsPanel: () => {
        set((state) => ({
          settings: { ...state.settings, artifactsPanelOpen: !state.settings.artifactsPanelOpen }
        }))
      },

      setAgentRunning: (running: boolean) => set({ agentRunning: running }),
      setIsGenerating: (generating: boolean) => set({ isGenerating: generating }),
      setAbortController: (controller: AbortController | null) => set({ abortController: controller }),
      setPendingSessionId: (id: string | null) => set({ pendingSessionId: id }),
      setConnectionStatus: (status: ConnectionStatus) => set({ connectionStatus: status }),

      addToast: (toast: Omit<Toast, 'id'>) => {
        const id = crypto.randomUUID()
        set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }))
        // Auto-remove after duration
        const duration = toast.duration || 4000
        setTimeout(() => {
          set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
        }, duration)
      },

      removeToast: (id: string) => {
        set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
      },

      setCommandPaletteOpen: (open: boolean) => set({ commandPaletteOpen: open }),

      addTeam: (team: Omit<Team, 'id' | 'createdAt'>) => {
        const id = crypto.randomUUID()
        set((state) => ({
          teams: [...state.teams, { ...team, id, createdAt: Date.now() }]
        }))
        return id
      },

      removeTeam: (id: string) => {
        set((state) => ({ teams: state.teams.filter((t) => t.id !== id) }))
      },

      updateTeam: (id: string, partial: Partial<Team>) => {
        set((state) => ({
          teams: state.teams.map((t) => t.id === id ? { ...t, ...partial } : t)
        }))
      },

      // Projects
      addProject: (name: string, projectPath: string) => {
        const id = crypto.randomUUID()
        set((state) => ({
          projects: [...state.projects, { id, name, path: projectPath, sessions: [], createdAt: Date.now() }],
          currentProjectId: id,
          projectFilesOpen: true,
        }))
        return id
      },

      removeProject: (id: string) => {
        set((state) => ({
          projects: state.projects.filter((p) => p.id !== id),
          currentProjectId: state.currentProjectId === id ? null : state.currentProjectId,
          projectFilesOpen: state.currentProjectId === id ? false : state.projectFilesOpen,
          fileTree: state.currentProjectId === id ? [] : state.fileTree,
        }))
      },

      setCurrentProject: (id: string | null) => {
        set({ currentProjectId: id, fileTree: [] })
        if (id) {
          set({ projectFilesOpen: true })
        }
      },

      toggleProjectFiles: () => {
        set((state) => ({ projectFilesOpen: !state.projectFilesOpen }))
      },

      setFileTree: (tree: FileTreeNode[]) => {
        set({ fileTree: tree })
      },

      linkSessionToProject: (projectId: string, sessionId: string) => {
        set((state) => ({
          projects: state.projects.map((p) =>
            p.id === projectId
              ? { ...p, sessions: [...new Set([...p.sessions, sessionId])] }
              : p
          )
        }))
      },

      // Dynamic config: fetch models & agents from backend API
      fetchRemoteConfig: async () => {
        const state = get()
        const baseUrl = state.settings.agentMode === 'local'
          ? `http://127.0.0.1:${state.settings.agentLocalPort}`
          : state.settings.agentRemoteUrl

        if (!baseUrl) return

        // Fetch models
        try {
          const modelsResp = await fetch(`${baseUrl}/models`, { signal: AbortSignal.timeout(5000) })
          if (modelsResp.ok) {
            const data = await modelsResp.json()
            const models: ModelOption[] = (data.models || data || []).map((m: any) => ({
              id: m.id || m.model || m.name,
              name: m.name || m.id || m.model,
              provider: m.provider || (m.id?.startsWith('claude') ? 'anthropic' : 'openai'),
              icon: m.provider === 'anthropic' || m.id?.startsWith('claude') ? '◈' : '●',
            }))
            if (models.length > 0) {
              set({ remoteModels: models })
              // Update the mutable export for components that import directly
              AVAILABLE_MODELS.splice(0, AVAILABLE_MODELS.length, ...models)
            }
          }
        } catch { /* fallback to defaults */ }

        // Fetch agents/skills
        try {
          const agentsResp = await fetch(`${baseUrl}/agents`, { signal: AbortSignal.timeout(5000) })
          if (agentsResp.ok) {
            const data = await agentsResp.json()
            const agents: AgentOption[] = (data.agents || data || []).map((a: any) => ({
              id: a.id || a.name,
              name: a.name || a.id,
              description: a.description || '',
              icon: a.icon || '⊙',
            }))
            if (agents.length > 0) {
              set({ remoteAgents: agents })
              AVAILABLE_AGENTS.splice(0, AVAILABLE_AGENTS.length, ...agents)
            }
          }
        } catch {
          // Try /skills endpoint as fallback
          try {
            const skillsResp = await fetch(`${baseUrl}/skills`, { signal: AbortSignal.timeout(5000) })
            if (skillsResp.ok) {
              const data = await skillsResp.json()
              const skills = data.skills || data || []
              if (Array.isArray(skills) && skills.length > 0 && typeof skills[0] === 'object') {
                const agents: AgentOption[] = skills.map((s: any) => ({
                  id: s.id || s.name,
                  name: s.name || s.id,
                  description: s.description || '',
                  icon: s.icon || '⊙',
                }))
                set({ remoteAgents: agents })
                AVAILABLE_AGENTS.splice(0, AVAILABLE_AGENTS.length, ...agents)
              }
            }
          } catch { /* fallback to defaults */ }
        }
      },

      // Getter: returns remote models if available, otherwise defaults
      getModels: () => {
        const state = get()
        return state.remoteModels.length > 0 ? state.remoteModels : DEFAULT_MODELS
      },

      // Getter: returns remote agents if available, otherwise defaults
      getAgents: () => {
        const state = get()
        return state.remoteAgents.length > 0 ? state.remoteAgents : DEFAULT_AGENTS
      },
    }),
    {
      name: 'agent-desktop-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        projects: state.projects,
        currentProjectId: state.currentProjectId,
        teams: state.teams,
        settings: state.settings,
      })
    }
  )
)
