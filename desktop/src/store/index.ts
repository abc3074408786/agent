import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// 消息类型
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  model?: string
}

// 会话类型
export interface Session {
  id: string
  title: string
  messages: Message[]
  model: string
  agentType?: string
  createdAt: number
  updatedAt: number
}

// Agent 助手类型
export interface AgentPreset {
  id: string
  name: string
  description: string
  icon: string
  color: string
}

// 团队成员类型
export interface TeamMember {
  agentId: string
  agentName: string
  icon: string
  model: string
  role: 'leader' | 'member'
}

// 团队类型
export interface Team {
  id: string
  name: string
  description: string
  leader: TeamMember
  members: TeamMember[]
  project?: string
  createdAt: number
}

// 设置类型
export interface Settings {
  // LLM 模式
  llmMode: 'user_key' | 'proxy'
  // 用户自带 Key
  openaiKey: string
  anthropicKey: string
  // 代理模式
  proxyUrl: string
  proxyKey: string
  // Agent 配置
  agentMode: 'local' | 'remote'
  agentLocalPort: number
  agentRemoteUrl: string
  // RAG 配置
  ragUrl: string
  ragKey: string
  // 默认模型
  defaultModel: string
  // 主题
  theme: 'light' | 'dark'
}

// 全局状态
interface AppState {
  // 会话
  sessions: Session[]
  currentSessionId: string | null
  // 团队
  teams: Team[]
  // 设置
  settings: Settings
  // Agent 状态（不持久化）
  agentRunning: boolean
  // 加载/生成状态（不持久化）
  isGenerating: boolean
  abortController: AbortController | null
  // 待处理消息标记（从 WelcomePage 跳转时用）
  pendingSessionId: string | null
  // 操作
  createSession: (agentType?: string) => string
  deleteSession: (id: string) => void
  setCurrentSession: (id: string) => void
  addMessage: (sessionId: string, message: Message) => void
  updateLastMessage: (sessionId: string, content: string) => void
  appendToLastMessage: (sessionId: string, chunk: string) => void
  updateSettings: (settings: Partial<Settings>) => void
  setAgentRunning: (running: boolean) => void
  setIsGenerating: (generating: boolean) => void
  setAbortController: (controller: AbortController | null) => void
  setPendingSessionId: (id: string | null) => void
  // 团队操作
  addTeam: (team: Omit<Team, 'id' | 'createdAt'>) => string
  removeTeam: (id: string) => void
  updateTeam: (id: string, partial: Partial<Team>) => void
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
  theme: 'light'
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      teams: [],
      settings: defaultSettings,
      agentRunning: false,
      isGenerating: false,
      abortController: null,
      pendingSessionId: null,

      createSession: (agentType?: string) => {
        const id = crypto.randomUUID()
        const session: Session = {
          id,
          title: '新对话',
          messages: [],
          model: get().settings.defaultModel,
          agentType,
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
            // 用第一条用户消息作为标题
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
              messages[messages.length - 1] = {
                ...messages[messages.length - 1],
                content
              }
            }
            return { ...s, messages, updatedAt: Date.now() }
          })
        }))
      },

      // 新增：追加模式更新（避免竞态）
      appendToLastMessage: (sessionId: string, chunk: string) => {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s
            const messages = [...s.messages]
            if (messages.length > 0) {
              const lastMsg = messages[messages.length - 1]
              messages[messages.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + chunk
              }
            }
            return { ...s, messages, updatedAt: Date.now() }
          })
        }))
      },

      updateSettings: (partial: Partial<Settings>) => {
        set((state) => ({
          settings: { ...state.settings, ...partial }
        }))
      },

      setAgentRunning: (running: boolean) => {
        set({ agentRunning: running })
      },

      setIsGenerating: (generating: boolean) => {
        set({ isGenerating: generating })
      },

      setAbortController: (controller: AbortController | null) => {
        set({ abortController: controller })
      },

      setPendingSessionId: (id: string | null) => {
        set({ pendingSessionId: id })
      },

      // 团队操作
      addTeam: (team: Omit<Team, 'id' | 'createdAt'>) => {
        const id = crypto.randomUUID()
        const newTeam: Team = {
          ...team,
          id,
          createdAt: Date.now()
        }
        set((state) => ({
          teams: [...state.teams, newTeam]
        }))
        return id
      },

      removeTeam: (id: string) => {
        set((state) => ({
          teams: state.teams.filter((t) => t.id !== id)
        }))
      },

      updateTeam: (id: string, partial: Partial<Team>) => {
        set((state) => ({
          teams: state.teams.map((t) => t.id === id ? { ...t, ...partial } : t)
        }))
      }
    }),
    {
      name: 'agent-desktop-storage',
      storage: createJSONStorage(() => localStorage),
      // 只持久化这些字段，排除运行时状态
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        teams: state.teams,
        settings: state.settings
      })
    }
  )
)
