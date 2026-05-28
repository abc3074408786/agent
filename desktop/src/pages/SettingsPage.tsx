import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Eye, EyeOff, Plus, Minus, Pencil, ChevronRight, ChevronDown,
  ToggleLeft, ToggleRight, ArrowLeft, Moon, Sun,
  Bot, Cpu, Users, Zap, Monitor, Globe, PawPrint, Layers, Info
} from 'lucide-react'
import { useAppStore, Settings } from '../store'

// 设置导航
type SettingsSection = 'agents' | 'models' | 'assistants' | 'extensions' | 'display' | 'remote' | 'pet' | 'system' | 'about'

interface NavGroup {
  label: string
  items: { id: SettingsSection; label: string; icon: React.ReactNode }[]
}

const navGroups: NavGroup[] = [
  {
    label: 'AI 核心',
    items: [
      { id: 'agents', label: 'Agents', icon: <Bot size={16} /> },
      { id: 'models', label: '模型', icon: <Cpu size={16} /> },
      { id: 'assistants', label: '助手', icon: <Users size={16} /> },
      { id: 'extensions', label: '能力扩展', icon: <Zap size={16} /> },
    ]
  },
  {
    label: '应用',
    items: [
      { id: 'display', label: '显示', icon: <Monitor size={16} /> },
      { id: 'remote', label: '远程连接', icon: <Globe size={16} /> },
      { id: 'pet', label: '桌面宠物', icon: <PawPrint size={16} /> },
      { id: 'system', label: '系统', icon: <Layers size={16} /> },
    ]
  },
  {
    label: '其他',
    items: [
      { id: 'about', label: '关于', icon: <Info size={16} /> },
    ]
  }
]

// Agent 卡片数据
interface AgentItem {
  id: string
  name: string
  icon: string
  detected: boolean
}

const localAgents: AgentItem[] = [
  { id: 'agent_cli', name: 'Agent CLI', icon: '⊙', detected: true },
  { id: 'claude_code', name: 'Claude Code', icon: '🌸', detected: true },
  { id: 'codex_cli', name: 'Codex CLI', icon: '⊙', detected: true },
  { id: 'gemini_cli', name: 'Gemini CLI', icon: '✦', detected: true },
  { id: 'rag_agent', name: 'RAG Agent', icon: '📚', detected: true },
]

// 模型数据
interface ModelItem {
  id: string
  name: string
  enabled: boolean
  expanded: boolean
}

export default function SettingsPage() {
  const { settings, updateSettings } = useAppStore()
  const [activeSection, setActiveSection] = useState<SettingsSection>('agents')
  const navigate = useNavigate()

  return (
    <div className="flex h-full overflow-hidden bg-white">
      {/* 左侧导航 */}
      <div className="w-[200px] h-full bg-gray-50/80 border-r border-gray-100 flex flex-col">
        {/* 导航分组 */}
        <nav className="flex-1 overflow-y-auto px-3 pt-4 pb-4">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-3 mb-1.5 text-xs text-blue-500 font-medium">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setActiveSection(item.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-all ${
                      activeSection === item.id
                        ? 'bg-gray-200/80 text-gray-900 font-medium'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <span className={activeSection === item.id ? 'text-gray-700' : 'text-gray-400'}>
                      {item.icon}
                    </span>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* 底部：返回聊天 + 暗色切换 */}
        <div className="px-3 py-3 border-t border-gray-100 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-gray-800 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft size={14} />
            返回聊天
          </button>
          <button
            onClick={() => updateSettings({ theme: settings.theme === 'light' ? 'dark' : 'light' })}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            {settings.theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
          </button>
        </div>
      </div>

      {/* 右侧内容区 */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl p-8">
          {activeSection === 'agents' && <AgentsSection />}
          {activeSection === 'models' && <ModelsSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'assistants' && <AssistantsSection />}
          {activeSection === 'extensions' && <ExtensionsSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'display' && <DisplaySection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'remote' && <RemoteSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'pet' && <PlaceholderSection title="桌面宠物" description="桌面宠物设置（即将推出）" />}
          {activeSection === 'system' && <SystemSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'about' && <AboutSection />}
        </div>
      </div>
    </div>
  )
}

// ============================================================
// Agents 页 - 卡片网格
// ============================================================
function AgentsSection() {
  const navigate = useNavigate()

  return (
    <div>
      {/* 标题 + 蓝色下划线 */}
      <div className="mb-6">
        <h3 className="text-xl font-bold text-gray-800 pb-2 border-b-2 border-blue-500 inline-block">
          本地 Agents
        </h3>
      </div>

      {/* 灰色提示条 */}
      <div className="mb-6 px-4 py-3 bg-gray-100 rounded-lg">
        <p className="text-sm text-gray-600">
          Agent CLI 是内置 Agent，App 自带无需安装；其他 Agent 需先在本地安装对应 CLI 才能被识别。识别自定义 Agent
        </p>
      </div>

      {/* 已检测标签 */}
      <p className="text-sm text-gray-500 mb-4">已检测</p>

      {/* Agent 卡片网格 */}
      <div className="grid grid-cols-5 gap-4">
        {localAgents.map((agent) => (
          <div
            key={agent.id}
            className="flex flex-col items-center p-5 bg-white rounded-xl border border-gray-150 hover:border-gray-200 hover:shadow-sm transition-all"
          >
            {/* 图标 */}
            <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center mb-3 text-2xl">
              {agent.icon}
            </div>
            {/* 名称 */}
            <p className="text-sm font-medium text-gray-800 mb-1">{agent.name}</p>
            {/* 状态 */}
            <p className="text-xs text-gray-400 mb-3">已检测</p>
            {/* 按钮 */}
            <button
              onClick={() => navigate('/')}
              className="w-full py-1.5 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              开始对话
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================
// 模型页 - 列表 + 开关
// ============================================================
function ModelsSection({ settings, updateSettings }: SettingsProps) {
  const [models, setModels] = useState<ModelItem[]>([
    { id: '1', name: 'GPT-4o', enabled: true, expanded: false },
    { id: '2', name: 'Claude Sonnet', enabled: true, expanded: false },
    { id: '3', name: '自定义', enabled: true, expanded: false },
  ])

  const toggleEnabled = (id: string) => {
    setModels(models.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m))
  }

  const toggleExpand = (id: string) => {
    setModels(models.map(m => m.id === id ? { ...m, expanded: !m.expanded } : m))
  }

  const addModel = () => {
    setModels([...models, {
      id: crypto.randomUUID(),
      name: '自定义',
      enabled: true,
      expanded: true
    }])
  }

  const removeModel = (id: string) => {
    setModels(models.filter(m => m.id !== id))
  }

  return (
    <div>
      {/* 标题行 */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-gray-800">模型</h3>
        <div className="flex items-center gap-2">
          <button className="px-4 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            清除状态
          </button>
          <button
            onClick={addModel}
            className="flex items-center gap-1 px-4 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Plus size={13} />
            添加模型
          </button>
        </div>
      </div>

      {/* 提示 */}
      <div className="mb-5 px-4 py-3 bg-gray-100 rounded-lg">
        <p className="text-sm text-gray-600">
          说明：目前仅 Agent CLI 支持自定义模型。
        </p>
      </div>

      {/* 模型列表 */}
      <div className="space-y-2">
        {models.map((model) => (
          <div key={model.id} className="border border-gray-150 rounded-xl overflow-hidden bg-white">
            {/* 模型行 */}
            <div className="flex items-center px-4 py-3.5">
              {/* 展开箭头 */}
              <button
                onClick={() => toggleExpand(model.id)}
                className="p-1 mr-2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                {model.expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </button>

              {/* 名称 */}
              <span className="flex-1 text-sm font-medium text-gray-700">{model.name}</span>

              {/* 操作按钮 */}
              <div className="flex items-center gap-2">
                {/* 开关 */}
                <button
                  onClick={() => toggleEnabled(model.id)}
                  className={`transition-colors ${model.enabled ? 'text-blue-500' : 'text-gray-300'}`}
                >
                  {model.enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
                </button>
                {/* + */}
                <button className="p-1 text-gray-400 hover:text-gray-600 transition-colors">
                  <Plus size={15} />
                </button>
                {/* - */}
                <button
                  onClick={() => removeModel(model.id)}
                  className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                >
                  <Minus size={15} />
                </button>
                {/* 编辑 */}
                <button
                  onClick={() => toggleExpand(model.id)}
                  className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <Pencil size={13} />
                </button>
              </div>
            </div>

            {/* 展开详情 */}
            {model.expanded && (
              <div className="px-4 pb-4 pt-2 border-t border-gray-100 space-y-3">
                <TextInput label="模型名称" value={model.name} onChange={() => {}} placeholder="模型名称" />
                <TextInput label="API Base URL" value="" onChange={() => {}} placeholder="https://api.openai.com/v1" />
                <PasswordInput label="API Key" value="" onChange={() => {}} placeholder="sk-..." />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================
// 助手页
// ============================================================
function AssistantsSection() {
  return (
    <div>
      <h3 className="text-xl font-bold text-gray-800 mb-6">助手</h3>
      <div className="px-4 py-3 bg-gray-100 rounded-lg">
        <p className="text-sm text-gray-600">管理可用的 Agent 助手预设，支持自定义 Prompt 和工具配置。</p>
      </div>
    </div>
  )
}

// ============================================================
// 能力扩展
// ============================================================
function ExtensionsSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-gray-800 mb-6">能力扩展</h3>

      <div className="space-y-4">
        {/* RAG */}
        <div className="p-5 bg-white rounded-xl border border-gray-150">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">📚</span>
            <div>
              <p className="text-sm font-semibold text-gray-800">RAG 知识库</p>
              <p className="text-xs text-gray-500">远程检索增强生成服务</p>
            </div>
          </div>
          <div className="space-y-3">
            <TextInput label="服务地址" value={settings.ragUrl} onChange={(v) => updateSettings({ ragUrl: v })} placeholder="https://rag.your-server.com" />
            <PasswordInput label="API Key" value={settings.ragKey} onChange={(v) => updateSettings({ ragKey: v })} placeholder="输入 RAG 服务的 Key" />
          </div>
        </div>

        {/* MCP */}
        <div className="p-5 bg-white rounded-xl border border-gray-150 opacity-50">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔌</span>
            <div>
              <p className="text-sm font-semibold text-gray-800">MCP 协议</p>
              <p className="text-xs text-gray-500">Model Context Protocol 集成（即将推出）</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// 显示设置
// ============================================================
function DisplaySection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-gray-800 mb-6">显示</h3>
      <div className="space-y-6">
        <div>
          <p className="text-sm font-medium text-gray-700 mb-3">主题</p>
          <div className="flex gap-3">
            <ThemeOption
              active={settings.theme === 'light'}
              onClick={() => updateSettings({ theme: 'light' })}
              label="浅色"
              icon={<Sun size={18} />}
            />
            <ThemeOption
              active={settings.theme === 'dark'}
              onClick={() => updateSettings({ theme: 'dark' })}
              label="深色"
              icon={<Moon size={18} />}
            />
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">字体大小</p>
          <div className="flex items-center gap-3">
            <input type="range" min="12" max="18" defaultValue="14" className="flex-1 accent-blue-500" />
            <span className="text-sm text-gray-500 w-10">14px</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// 远程连接
// ============================================================
function RemoteSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-gray-800 mb-6">远程连接</h3>
      <div className="space-y-4">
        <TextInput label="Agent 服务地址" value={settings.agentRemoteUrl} onChange={(v) => updateSettings({ agentRemoteUrl: v })} placeholder="https://agent.your-server.com" />
        <TextInput label="本地端口" value={String(settings.agentLocalPort)} onChange={(v) => updateSettings({ agentLocalPort: parseInt(v) || 8765 })} placeholder="8765" />
      </div>
    </div>
  )
}

// ============================================================
// 系统
// ============================================================
function SystemSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-gray-800 mb-6">系统</h3>
      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-150">
          <div>
            <p className="text-sm font-medium text-gray-700">开机自启</p>
            <p className="text-xs text-gray-400">系统启动时自动运行 Agent Desktop</p>
          </div>
          <button className="text-gray-300">
            <ToggleLeft size={24} />
          </button>
        </div>
        <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-150">
          <div>
            <p className="text-sm font-medium text-gray-700">最小化到托盘</p>
            <p className="text-xs text-gray-400">关闭窗口时最小化到系统托盘</p>
          </div>
          <button className="text-blue-500">
            <ToggleRight size={24} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// 关于
// ============================================================
function AboutSection() {
  return (
    <div>
      <h3 className="text-xl font-bold text-gray-800 mb-6">关于</h3>
      <div className="p-6 bg-white rounded-xl border border-gray-150">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center shadow-lg">
            <span className="text-white text-2xl font-bold">A</span>
          </div>
          <div>
            <h4 className="text-lg font-bold text-gray-800">Agent Desktop</h4>
            <p className="text-sm text-gray-500">v0.2.0</p>
          </div>
        </div>
        <div className="space-y-2 text-sm text-gray-600">
          <div className="flex justify-between py-2 border-b border-gray-100">
            <span>框架</span><span className="text-gray-800">Electron + React</span>
          </div>
          <div className="flex justify-between py-2 border-b border-gray-100">
            <span>Agent 版本</span><span className="text-gray-800">v0.2.0</span>
          </div>
          <div className="flex justify-between py-2 border-b border-gray-100">
            <span>内置工具</span><span className="text-gray-800">20 个</span>
          </div>
          <div className="flex justify-between py-2">
            <span>开源协议</span><span className="text-gray-800">MIT</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// 占位页
// ============================================================
function PlaceholderSection({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h3 className="text-xl font-bold text-gray-800 mb-4">{title}</h3>
      <div className="px-4 py-3 bg-gray-100 rounded-lg">
        <p className="text-sm text-gray-600">{description}</p>
      </div>
    </div>
  )
}

// ============================================================
// 通用子组件
// ============================================================
interface SettingsProps {
  settings: Settings
  updateSettings: (partial: Partial<Settings>) => void
}

function ThemeOption({ active, onClick, label, icon }: { active: boolean; onClick: () => void; label: string; icon: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-3 rounded-xl border-2 transition-all ${
        active ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-600 hover:border-gray-300'
      }`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}

function TextInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-600 mb-1 block">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
      />
    </div>
  )
}

function PasswordInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  const [visible, setVisible] = useState(false)
  return (
    <div>
      <label className="text-xs font-medium text-gray-600 mb-1 block">{label}</label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full px-3 py-2 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          {visible ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </div>
  )
}
