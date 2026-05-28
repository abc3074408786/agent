import { useState } from 'react'
import {
  Save, Check, Eye, EyeOff, Wifi, WifiOff, Server, Key, Database,
  Palette, Bot, Zap, Monitor, Info, ArrowLeft, Moon, Sun,
  Plus, Minus, Pencil, ChevronRight, ChevronDown, ToggleLeft, ToggleRight,
  Globe, Cpu, Layers
} from 'lucide-react'
import { useAppStore, Settings } from '../store'
import { useNavigate } from 'react-router-dom'

// 设置导航分组
type SettingsSection = 'models' | 'assistants' | 'extensions' | 'agent' | 'connection' | 'theme' | 'interface' | 'about'

interface NavGroup {
  label: string
  items: { id: SettingsSection; label: string; icon: React.ReactNode }[]
}

const navGroups: NavGroup[] = [
  {
    label: 'AI 核心',
    items: [
      { id: 'models', label: '模型管理', icon: <Cpu size={16} /> },
      { id: 'assistants', label: '助手配置', icon: <Bot size={16} /> },
      { id: 'extensions', label: '能力扩展', icon: <Zap size={16} /> }
    ]
  },
  {
    label: '服务',
    items: [
      { id: 'agent', label: 'Agent 服务', icon: <Server size={16} /> },
      { id: 'connection', label: '连接管理', icon: <Globe size={16} /> }
    ]
  },
  {
    label: '外观',
    items: [
      { id: 'theme', label: '主题', icon: <Palette size={16} /> },
      { id: 'interface', label: '界面', icon: <Monitor size={16} /> }
    ]
  },
  {
    label: '其他',
    items: [
      { id: 'about', label: '关于', icon: <Info size={16} /> }
    ]
  }
]


// 模型数据类型
interface ModelConfig {
  id: string
  name: string
  provider: string
  apiKey: string
  baseUrl: string
  enabled: boolean
  isDefault: boolean
}

export default function SettingsPage() {
  const { settings, updateSettings } = useAppStore()
  const [activeSection, setActiveSection] = useState<SettingsSection>('models')
  const [saved, setSaved] = useState(false)
  const navigate = useNavigate()

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="flex h-full overflow-hidden bg-gray-50/50">
      {/* 左侧导航 */}
      <div className="w-52 h-full bg-white border-r border-gray-100 flex flex-col">
        {/* 顶部标题 */}
        <div className="px-5 pt-5 pb-3">
          <h2 className="text-lg font-bold text-gray-800">设置</h2>
        </div>

        {/* 导航分组 */}
        <nav className="flex-1 overflow-y-auto px-3 pb-4">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-3 mb-1 text-xs font-medium text-primary-500 uppercase tracking-wider">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setActiveSection(item.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-all ${
                      activeSection === item.id
                        ? 'bg-primary-50 text-primary-700 font-medium shadow-sm'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800'
                    }`}
                  >
                    <span className={activeSection === item.id ? 'text-primary-500' : 'text-gray-400'}>
                      {item.icon}
                    </span>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>


        {/* 底部操作栏 */}
        <div className="px-3 py-3 border-t border-gray-100 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-gray-800 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <ArrowLeft size={14} />
            返回聊天
          </button>
          <button
            onClick={() => updateSettings({ theme: settings.theme === 'light' ? 'dark' : 'light' })}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {settings.theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          </button>
        </div>
      </div>

      {/* 右侧内容区 */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-8">
          {activeSection === 'models' && <ModelsSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'assistants' && <AssistantsSection />}
          {activeSection === 'extensions' && <ExtensionsSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'agent' && <AgentSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'connection' && <ConnectionSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'theme' && <ThemeSection settings={settings} updateSettings={updateSettings} />}
          {activeSection === 'interface' && <InterfaceSection />}
          {activeSection === 'about' && <AboutSection />}
        </div>
      </div>
    </div>
  )
}


// ============================================================
// 模型管理（核心特色：卡片列表 + 展开编辑 + 状态指示灯）
// ============================================================

function ModelsSection({ settings, updateSettings }: SettingsProps) {
  const [models, setModels] = useState<ModelConfig[]>([
    { id: '1', name: 'GPT-4o', provider: 'openai', apiKey: '', baseUrl: 'https://api.openai.com/v1', enabled: true, isDefault: true },
    { id: '2', name: 'Claude Sonnet 4', provider: 'anthropic', apiKey: '', baseUrl: 'https://api.anthropic.com', enabled: true, isDefault: false },
    { id: '3', name: '自定义模型', provider: 'custom', apiKey: '', baseUrl: '', enabled: false, isDefault: false }
  ])
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id)
  }

  const toggleEnabled = (id: string) => {
    setModels(models.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m))
  }

  const addModel = () => {
    const newModel: ModelConfig = {
      id: crypto.randomUUID(),
      name: '新模型',
      provider: 'custom',
      apiKey: '',
      baseUrl: '',
      enabled: true,
      isDefault: false
    }
    setModels([...models, newModel])
    setExpandedId(newModel.id)
  }

  const removeModel = (id: string) => {
    setModels(models.filter(m => m.id !== id))
  }

  const updateModel = (id: string, partial: Partial<ModelConfig>) => {
    setModels(models.map(m => m.id === id ? { ...m, ...partial } : m))
  }

  return (
    <div>
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-gray-800">模型</h3>
          <p className="text-sm text-gray-500 mt-1">管理你的 AI 模型配置</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={addModel}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors border border-primary-200"
          >
            <Plus size={14} />
            添加模型
          </button>
        </div>
      </div>


      {/* 提示信息 */}
      <div className="mb-4 px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100">
        <p className="text-sm text-blue-700">
          支持 OpenAI、Anthropic 及任何兼容 OpenAI 格式的自定义模型。
        </p>
      </div>

      {/* 模型列表 */}
      <div className="space-y-2">
        {models.map((model) => (
          <div
            key={model.id}
            className={`rounded-xl border transition-all ${
              expandedId === model.id
                ? 'border-primary-200 bg-white shadow-sm'
                : 'border-gray-150 bg-white hover:border-gray-200'
            }`}
          >
            {/* 模型行 */}
            <div className="flex items-center px-4 py-3.5">
              {/* 展开箭头 */}
              <button
                onClick={() => toggleExpand(model.id)}
                className="p-1 mr-2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                {expandedId === model.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </button>

              {/* 状态指示灯 */}
              <span className={`w-2 h-2 rounded-full mr-3 ${model.enabled ? 'bg-green-400' : 'bg-gray-300'}`} />

              {/* 模型名称 */}
              <span className="flex-1 text-sm font-medium text-gray-700">{model.name}</span>

              {/* 默认标签 */}
              {model.isDefault && (
                <span className="px-2 py-0.5 text-xs font-medium text-primary-600 bg-primary-50 rounded-full mr-3">
                  默认
                </span>
              )}

              {/* 操作按钮 */}
              <div className="flex items-center gap-1">
                {/* 启用/禁用开关 */}
                <button
                  onClick={() => toggleEnabled(model.id)}
                  className={`p-1 transition-colors ${model.enabled ? 'text-primary-500' : 'text-gray-300'}`}
                >
                  {model.enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                </button>
                {/* 删除 */}
                <button
                  onClick={() => removeModel(model.id)}
                  className="p-1 text-gray-300 hover:text-red-500 transition-colors"
                >
                  <Minus size={16} />
                </button>
                {/* 编辑 */}
                <button
                  onClick={() => toggleExpand(model.id)}
                  className="p-1 text-gray-300 hover:text-gray-600 transition-colors"
                >
                  <Pencil size={14} />
                </button>
              </div>
            </div>


            {/* 展开详情 */}
            {expandedId === model.id && (
              <div className="px-4 pb-4 pt-2 border-t border-gray-100 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <TextInput
                    label="模型名称"
                    value={model.name}
                    onChange={(v) => updateModel(model.id, { name: v })}
                    placeholder="GPT-4o"
                  />
                  <div>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">Provider</label>
                    <select
                      value={model.provider}
                      onChange={(e) => updateModel(model.id, { provider: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="custom">自定义 (OpenAI 兼容)</option>
                    </select>
                  </div>
                </div>
                <TextInput
                  label="API Base URL"
                  value={model.baseUrl}
                  onChange={(v) => updateModel(model.id, { baseUrl: v })}
                  placeholder="https://api.openai.com/v1"
                />
                <PasswordInput
                  label="API Key"
                  value={model.apiKey}
                  onChange={(v) => updateModel(model.id, { apiKey: v })}
                  placeholder="sk-..."
                />
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => setModels(models.map(m => ({ ...m, isDefault: m.id === model.id })))}
                    className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                      model.isDefault
                        ? 'bg-primary-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {model.isDefault ? '当前默认' : '设为默认'}
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}


// ============================================================
// 助手配置
// ============================================================

function AssistantsSection() {
  const assistants = [
    { id: 'code_reviewer', name: '代码审查', icon: '🔍', enabled: true },
    { id: 'architect', name: '架构师', icon: '🏗️', enabled: true },
    { id: 'python_developer', name: 'Python 开发', icon: '🐍', enabled: true },
    { id: 'bug_fixer', name: 'Bug 修复', icon: '🐛', enabled: true },
    { id: 'full_stack', name: '全栈开发', icon: '⚡', enabled: false },
    { id: 'security_auditor', name: '安全审计', icon: '🛡️', enabled: true },
    { id: 'agentic_rag', name: 'RAG 知识库', icon: '📚', enabled: true },
  ]
  const [list, setList] = useState(assistants)

  const toggle = (id: string) => {
    setList(list.map(a => a.id === id ? { ...a, enabled: !a.enabled } : a))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-gray-800">助手</h3>
          <p className="text-sm text-gray-500 mt-1">管理首页展示的 Agent 助手</p>
        </div>
        <button className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors border border-primary-200">
          <Plus size={14} />
          添加助手
        </button>
      </div>

      <div className="space-y-2">
        {list.map((a) => (
          <div key={a.id} className="flex items-center px-4 py-3 bg-white rounded-xl border border-gray-150 hover:border-gray-200 transition-all">
            <span className="text-xl mr-3">{a.icon}</span>
            <span className="flex-1 text-sm font-medium text-gray-700">{a.name}</span>
            <button
              onClick={() => toggle(a.id)}
              className={`p-1 transition-colors ${a.enabled ? 'text-primary-500' : 'text-gray-300'}`}
            >
              {a.enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
            </button>
            <button className="p-1 ml-1 text-gray-300 hover:text-gray-600 transition-colors">
              <Pencil size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}


// ============================================================
// 能力扩展（RAG / 插件）
// ============================================================

function ExtensionsSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <div className="mb-6">
        <h3 className="text-xl font-bold text-gray-800">能力扩展</h3>
        <p className="text-sm text-gray-500 mt-1">为 Agent 添加额外能力</p>
      </div>

      {/* RAG 知识库 */}
      <div className="mb-6 p-5 bg-white rounded-xl border border-gray-150">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-indigo-50 flex items-center justify-center">
            <Database size={18} className="text-indigo-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">RAG 知识库</p>
            <p className="text-xs text-gray-500">远程检索增强生成服务</p>
          </div>
        </div>
        <div className="space-y-3">
          <TextInput
            label="服务地址"
            value={settings.ragUrl}
            onChange={(v) => updateSettings({ ragUrl: v })}
            placeholder="https://rag.your-server.com"
          />
          <PasswordInput
            label="API Key"
            value={settings.ragKey}
            onChange={(v) => updateSettings({ ragKey: v })}
            placeholder="输入 RAG 服务的 Key"
          />
        </div>
      </div>

      {/* MCP 协议（预留） */}
      <div className="p-5 bg-white rounded-xl border border-gray-150 opacity-60">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-purple-50 flex items-center justify-center">
            <Layers size={18} className="text-purple-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">MCP 协议</p>
            <p className="text-xs text-gray-500">Model Context Protocol 集成（即将推出）</p>
          </div>
        </div>
      </div>
    </div>
  )
}


// ============================================================
// Agent 服务
// ============================================================

function AgentSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <div className="mb-6">
        <h3 className="text-xl font-bold text-gray-800">Agent 服务</h3>
        <p className="text-sm text-gray-500 mt-1">配置 Agent 的运行方式</p>
      </div>

      {/* 模式选择 */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <ModeCard
          active={settings.agentMode === 'local'}
          onClick={() => updateSettings({ agentMode: 'local' })}
          icon={<WifiOff size={20} />}
          title="本地运行"
          description="启动本地 Python Agent"
        />
        <ModeCard
          active={settings.agentMode === 'remote'}
          onClick={() => updateSettings({ agentMode: 'remote' })}
          icon={<Wifi size={20} />}
          title="远程服务"
          description="连接远程 API"
        />
      </div>

      {settings.agentMode === 'local' && (
        <div className="p-5 bg-white rounded-xl border border-gray-150 space-y-4">
          <TextInput
            label="本地端口"
            value={String(settings.agentLocalPort)}
            onChange={(v) => updateSettings({ agentLocalPort: parseInt(v) || 8765 })}
            placeholder="8765"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.electronAPI?.agent.start(settings.agentLocalPort)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-500 rounded-lg hover:bg-green-600 transition-colors"
            >
              <Cpu size={14} />
              启动 Agent
            </button>
            <button
              onClick={() => window.electronAPI?.agent.stop()}
              className="px-4 py-2 text-sm text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors border border-red-200"
            >
              停止
            </button>
          </div>
          <p className="text-xs text-gray-400">
            需要 Python 3.10+ 环境，Agent 运行在 127.0.0.1:{settings.agentLocalPort}
          </p>
        </div>
      )}

      {settings.agentMode === 'remote' && (
        <div className="p-5 bg-white rounded-xl border border-gray-150 space-y-4">
          <TextInput
            label="Agent 服务地址"
            value={settings.agentRemoteUrl}
            onChange={(v) => updateSettings({ agentRemoteUrl: v })}
            placeholder="https://agent.your-server.com"
          />
        </div>
      )}
    </div>
  )
}


// ============================================================
// 连接管理
// ============================================================

function ConnectionSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <div className="mb-6">
        <h3 className="text-xl font-bold text-gray-800">连接管理</h3>
        <p className="text-sm text-gray-500 mt-1">API 代理和网络设置</p>
      </div>

      {/* LLM 模式 */}
      <div className="mb-6">
        <p className="text-sm font-medium text-gray-700 mb-3">LLM 连接模式</p>
        <div className="grid grid-cols-2 gap-3">
          <ModeCard
            active={settings.llmMode === 'user_key'}
            onClick={() => updateSettings({ llmMode: 'user_key' })}
            icon={<Key size={20} />}
            title="自有 API Key"
            description="直连 OpenAI / Anthropic"
          />
          <ModeCard
            active={settings.llmMode === 'proxy'}
            onClick={() => updateSettings({ llmMode: 'proxy' })}
            icon={<Server size={20} />}
            title="统一代理"
            description="通过代理服务器转发"
          />
        </div>
      </div>

      {settings.llmMode === 'user_key' && (
        <div className="p-5 bg-white rounded-xl border border-gray-150 space-y-3">
          <PasswordInput
            label="OpenAI API Key"
            value={settings.openaiKey}
            onChange={(v) => updateSettings({ openaiKey: v })}
            placeholder="sk-..."
          />
          <PasswordInput
            label="Anthropic API Key"
            value={settings.anthropicKey}
            onChange={(v) => updateSettings({ anthropicKey: v })}
            placeholder="sk-ant-..."
          />
        </div>
      )}

      {settings.llmMode === 'proxy' && (
        <div className="p-5 bg-white rounded-xl border border-gray-150 space-y-3">
          <TextInput
            label="代理服务地址"
            value={settings.proxyUrl}
            onChange={(v) => updateSettings({ proxyUrl: v })}
            placeholder="https://api.your-proxy.com"
          />
          <PasswordInput
            label="代理 API Key"
            value={settings.proxyKey}
            onChange={(v) => updateSettings({ proxyKey: v })}
            placeholder="输入代理服务的 Key"
          />
        </div>
      )}
    </div>
  )
}


// ============================================================
// 主题
// ============================================================

function ThemeSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <div className="mb-6">
        <h3 className="text-xl font-bold text-gray-800">主题</h3>
        <p className="text-sm text-gray-500 mt-1">自定义应用外观</p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <ThemeCard
          active={settings.theme === 'light'}
          onClick={() => updateSettings({ theme: 'light' })}
          title="浅色"
          preview="bg-white border-gray-200"
          icon={<Sun size={20} />}
        />
        <ThemeCard
          active={settings.theme === 'dark'}
          onClick={() => updateSettings({ theme: 'dark' })}
          title="深色"
          preview="bg-gray-800 border-gray-700"
          icon={<Moon size={20} />}
        />
        <ThemeCard
          active={false}
          onClick={() => {}}
          title="跟随系统"
          preview="bg-gradient-to-br from-white to-gray-800 border-gray-300"
          icon={<Monitor size={20} />}
          disabled
        />
      </div>
    </div>
  )
}

function ThemeCard({ active, onClick, title, preview, icon, disabled }: {
  active: boolean; onClick: () => void; title: string; preview: string; icon: React.ReactNode; disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`p-4 rounded-xl border-2 text-center transition-all ${
        disabled ? 'opacity-40 cursor-not-allowed border-gray-200' :
        active ? 'border-primary-500 bg-primary-50 shadow-sm' : 'border-gray-200 hover:border-gray-300 bg-white'
      }`}
    >
      <div className={`w-full h-16 rounded-lg mb-3 border ${preview}`} />
      <div className={`flex items-center justify-center gap-1.5 ${active ? 'text-primary-600' : 'text-gray-600'}`}>
        {icon}
        <span className="text-sm font-medium">{title}</span>
      </div>
    </button>
  )
}


// ============================================================
// 界面设置
// ============================================================

function InterfaceSection() {
  return (
    <div>
      <div className="mb-6">
        <h3 className="text-xl font-bold text-gray-800">界面</h3>
        <p className="text-sm text-gray-500 mt-1">调整界面细节</p>
      </div>

      <div className="space-y-4 p-5 bg-white rounded-xl border border-gray-150">
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">字体大小</label>
          <div className="flex items-center gap-3">
            <input type="range" min="12" max="18" defaultValue="14" className="flex-1 accent-primary-500" />
            <span className="text-sm text-gray-500 w-10">14px</span>
          </div>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">侧边栏宽度</label>
          <div className="flex items-center gap-3">
            <input type="range" min="180" max="320" defaultValue="240" className="flex-1 accent-primary-500" />
            <span className="text-sm text-gray-500 w-14">240px</span>
          </div>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">消息气泡宽度</label>
          <div className="flex items-center gap-3">
            <input type="range" min="60" max="90" defaultValue="80" className="flex-1 accent-primary-500" />
            <span className="text-sm text-gray-500 w-10">80%</span>
          </div>
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
      <div className="mb-6">
        <h3 className="text-xl font-bold text-gray-800">关于</h3>
      </div>

      <div className="p-6 bg-white rounded-xl border border-gray-150">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-lg">
            <span className="text-white text-2xl font-bold">A</span>
          </div>
          <div>
            <h4 className="text-lg font-bold text-gray-800">Agent Desktop</h4>
            <p className="text-sm text-gray-500">v0.1.0</p>
          </div>
        </div>

        <div className="space-y-2 text-sm text-gray-600">
          <div className="flex justify-between py-2 border-b border-gray-100">
            <span>框架</span>
            <span className="text-gray-800">Electron + React</span>
          </div>
          <div className="flex justify-between py-2 border-b border-gray-100">
            <span>Agent 版本</span>
            <span className="text-gray-800">v0.2.0</span>
          </div>
          <div className="flex justify-between py-2 border-b border-gray-100">
            <span>内置工具</span>
            <span className="text-gray-800">20 个</span>
          </div>
          <div className="flex justify-between py-2 border-b border-gray-100">
            <span>技能包</span>
            <span className="text-gray-800">11 个</span>
          </div>
          <div className="flex justify-between py-2">
            <span>开源协议</span>
            <span className="text-gray-800">MIT</span>
          </div>
        </div>
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

function ModeCard({
  active,
  onClick,
  icon,
  title,
  description
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <button
      onClick={onClick}
      className={`p-4 rounded-xl border-2 text-left transition-all ${
        active
          ? 'border-primary-500 bg-primary-50 shadow-sm'
          : 'border-gray-200 hover:border-gray-300 bg-white'
      }`}
    >
      <div className={`mb-2 ${active ? 'text-primary-600' : 'text-gray-400'}`}>{icon}</div>
      <p className={`text-sm font-medium ${active ? 'text-primary-700' : 'text-gray-700'}`}>{title}</p>
      <p className="text-xs text-gray-500 mt-0.5">{description}</p>
    </button>
  )
}

function TextInput({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string
}) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-600 mb-1 block">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-gray-50/50"
      />
    </div>
  )
}

function PasswordInput({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string
}) {
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
          className="w-full px-3 py-2 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-gray-50/50"
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
