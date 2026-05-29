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

// Expert types (OmniWork-style Expert Marketplace)
export type ExpertCategory = 'content' | 'development' | 'business' | 'design' | 'media' | 'data' | 'operations'

export interface Expert {
  id: string
  name: string
  icon: string
  category: ExpertCategory
  description: string
  capabilities: string[]
  model?: string // preferred model
  systemPrompt?: string
  tools?: string[]
  source: 'builtin' | 'backend' | 'custom'
}

// Skill template types
export interface SkillStep {
  expertId: string
  prompt: string
  dependsOn?: string[] // step IDs
}

export interface SkillTemplate {
  id: string
  name: string
  description: string
  icon: string
  steps: SkillStep[]
  category: ExpertCategory
  autowork?: { enabled: boolean; cron?: string } // for automation
  createdAt: number
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
  // Permission mode
  permissionMode: 'default' | 'auto_edit' | 'full_auto'
  // Active CLI Agent (for ACP routing)
  activeCliAgent: 'none' | 'codex' | 'claude_code' | 'custom'
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
  // Experts & Skills
  experts: Expert[]
  hiredExpertIds: string[]
  skillTemplates: SkillTemplate[]
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
  // Actions: Experts & Skills
  hireExpert: (expertId: string) => void
  fireExpert: (expertId: string) => void
  addCustomExpert: (expert: Omit<Expert, 'id' | 'source'>) => string
  removeCustomExpert: (id: string) => void
  saveSkillTemplate: (template: Omit<SkillTemplate, 'id' | 'createdAt'>) => string
  removeSkillTemplate: (id: string) => void
  updateSkillTemplate: (id: string, partial: Partial<SkillTemplate>) => void
  getHiredExperts: () => Expert[]
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
  permissionMode: 'default',
  activeCliAgent: 'none',
}

// Builtin experts (OmniWork-style)
export const BUILTIN_EXPERTS: Expert[] = [
  // Content & Media
  { id: 'content-strategist', name: '内容策略师', icon: '📝', category: 'content', description: '跨平台内容策划、选题规划、爆款结构分析', capabilities: ['热点追踪', '选题策划', '内容结构优化', '平台适配'], source: 'builtin' },
  { id: 'video-director', name: '视频导演', icon: '🎬', category: 'media', description: '分镜拆解、视觉元素替换、BGM卡点同步', capabilities: ['分镜设计', '转场编排', '音画同步', '品牌元素适配'], source: 'builtin' },
  { id: 'music-producer', name: '音乐制作人', icon: '🎵', category: 'media', description: '配乐创作、音效设计、节奏卡点', capabilities: ['BGM创作', '音效设计', '节奏分析', '风格匹配'], source: 'builtin' },
  { id: 'copywriter', name: '文案大师', icon: '✍️', category: 'content', description: '广告文案、社媒文案、品牌故事', capabilities: ['标题优化', '故事叙述', '情感共鸣', '行动号召'], source: 'builtin' },
  { id: 'trend-monitor', name: '热点监控器', icon: '📡', category: 'content', description: '实时追踪全网热点话题，生成趋势报告', capabilities: ['多平台爬取', '趋势分析', '热度预测', '报告生成'], source: 'builtin' },
  // Development
  { id: 'python-expert', name: 'Python 专家', icon: '🐍', category: 'development', description: 'Python 最佳实践、高级特性、性能优化', capabilities: ['代码重构', '性能优化', '架构设计', '测试策略'], tools: ['file_read', 'file_write', 'bash_execute'], source: 'builtin' },
  { id: 'fullstack-dev', name: '全栈开发', icon: '🚀', category: 'development', description: '前端 + 后端 + DevOps 全链路开发', capabilities: ['React/Vue', 'Node/Python', 'Docker', 'CI/CD'], tools: ['file_read', 'file_write', 'bash_execute', 'git_commit'], source: 'builtin' },
  { id: 'code-reviewer', name: '代码审查', icon: '🔍', category: 'development', description: '代码质量、安全漏洞、性能瓶颈审查', capabilities: ['Bug检测', '安全审计', '性能分析', '最佳实践'], tools: ['file_read', 'grep_search'], source: 'builtin' },
  { id: 'devops-engineer', name: 'DevOps 工程师', icon: '⚙️', category: 'development', description: 'CI/CD、容器化、自动化部署', capabilities: ['Docker', 'Kubernetes', 'GitHub Actions', '监控'], tools: ['bash_execute', 'file_write'], source: 'builtin' },
  // Business & Analysis
  { id: 'business-analyst', name: '商业分析师', icon: '📊', category: 'business', description: '市场分析、竞品调研、商业计划书', capabilities: ['市场调研', '竞品分析', 'SWOT分析', '财务建模'], source: 'builtin' },
  { id: 'growth-hacker', name: '增长黑客', icon: '📈', category: 'business', description: '用户增长策略、A/B测试、漏斗优化', capabilities: ['增长实验', '数据分析', '用户留存', '病毒传播'], source: 'builtin' },
  { id: 'account-manager', name: '账号运营', icon: '👤', category: 'operations', description: '社媒账号运营、粉丝增长、互动优化', capabilities: ['内容日历', '互动策略', '数据复盘', '粉丝运营'], source: 'builtin' },
  // Design
  { id: 'ui-designer', name: 'UI 设计师', icon: '🎨', category: 'design', description: '界面设计、组件系统、视觉规范', capabilities: ['界面布局', '配色方案', '组件设计', '响应式'], source: 'builtin' },
  { id: 'ppt-expert', name: 'PPT 设计专家', icon: '📑', category: 'design', description: '专业演示文稿设计、数据可视化', capabilities: ['排版设计', '数据图表', '动画效果', '品牌规范'], source: 'builtin' },
  { id: 'visual-director', name: '视觉总监', icon: '👁️', category: 'design', description: '品牌视觉体系、广告创意、视觉叙事', capabilities: ['品牌设计', '广告创意', '视觉叙事', '素材管理'], source: 'builtin' },
  // Data
  { id: 'data-scientist', name: '数据科学家', icon: '🧮', category: 'data', description: '数据分析、建模、可视化', capabilities: ['统计分析', '机器学习', '数据可视化', 'A/B测试'], source: 'builtin' },
  { id: 'web-scraper', name: '数据采集专家', icon: '🕷️', category: 'data', description: '全网数据采集、清洗、结构化', capabilities: ['网页爬虫', '数据清洗', 'API对接', '定时采集'], source: 'builtin' },
  // Operations
  { id: 'project-manager', name: '项目经理', icon: '📋', category: 'operations', description: '项目规划、任务分解、进度跟踪', capabilities: ['需求分析', '任务拆解', '风险管理', '交付管理'], source: 'builtin' },
  { id: 'security-auditor', name: '安全审计', icon: '🛡️', category: 'development', description: '安全漏洞扫描、渗透测试建议', capabilities: ['漏洞扫描', '代码审计', '合规检查', '修复建议'], tools: ['file_read', 'grep_search', 'bash_execute'], source: 'builtin' },
  { id: 'game-developer', name: '游戏开发', icon: '🎮', category: 'development', description: '游戏逻辑、场景叙事、交互设计', capabilities: ['游戏设计', '关卡规划', 'Unity/UE', '叙事驱动'], source: 'builtin' },
]

export const EXPERT_CATEGORIES: Record<ExpertCategory, { label: string; icon: string }> = {
  content: { label: '内容创作', icon: '📝' },
  development: { label: '开发工程', icon: '💻' },
  business: { label: '商业分析', icon: '📊' },
  design: { label: '设计制作', icon: '🎨' },
  media: { label: '影音媒体', icon: '🎬' },
  data: { label: '数据智能', icon: '🧮' },
  operations: { label: '运营管理', icon: '📋' },
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
      experts: BUILTIN_EXPERTS,
      hiredExpertIds: [],
      skillTemplates: [],
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

      // Experts & Skills
      hireExpert: (expertId: string) => {
        set((state) => ({
          hiredExpertIds: [...new Set([...state.hiredExpertIds, expertId])]
        }))
      },

      fireExpert: (expertId: string) => {
        set((state) => ({
          hiredExpertIds: state.hiredExpertIds.filter((id) => id !== expertId)
        }))
      },

      addCustomExpert: (expert: Omit<Expert, 'id' | 'source'>) => {
        const id = 'custom-' + crypto.randomUUID().slice(0, 8)
        const newExpert: Expert = { ...expert, id, source: 'custom' }
        set((state) => ({
          experts: [...state.experts, newExpert],
          hiredExpertIds: [...state.hiredExpertIds, id]
        }))
        return id
      },

      removeCustomExpert: (id: string) => {
        set((state) => ({
          experts: state.experts.filter((e) => e.id !== id),
          hiredExpertIds: state.hiredExpertIds.filter((eid) => eid !== id)
        }))
      },

      saveSkillTemplate: (template: Omit<SkillTemplate, 'id' | 'createdAt'>) => {
        const id = crypto.randomUUID()
        set((state) => ({
          skillTemplates: [...state.skillTemplates, { ...template, id, createdAt: Date.now() }]
        }))
        return id
      },

      removeSkillTemplate: (id: string) => {
        set((state) => ({
          skillTemplates: state.skillTemplates.filter((s) => s.id !== id)
        }))
      },

      updateSkillTemplate: (id: string, partial: Partial<SkillTemplate>) => {
        set((state) => ({
          skillTemplates: state.skillTemplates.map((s) => s.id === id ? { ...s, ...partial } : s)
        }))
      },

      getHiredExperts: () => {
        const state = get()
        return state.experts.filter((e) => state.hiredExpertIds.includes(e.id))
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
        hiredExpertIds: state.hiredExpertIds,
        skillTemplates: state.skillTemplates,
        teams: state.teams,
        settings: state.settings,
      })
    }
  )
)
