import { useState } from 'react'
import { Save, Check, Eye, EyeOff, Wifi, WifiOff, Server, Key, Database, Palette } from 'lucide-react'
import { useAppStore, Settings } from '../store'

type SettingsTab = 'llm' | 'agent' | 'rag' | 'general'

export default function SettingsPage() {
  const { settings, updateSettings } = useAppStore()
  const [activeTab, setActiveTab] = useState<SettingsTab>('llm')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    // 持久化到 localStorage（后续可改为文件存储）
    localStorage.setItem('agent-desktop-settings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const tabs: { id: SettingsTab; label: string; icon: React.ReactNode }[] = [
    { id: 'llm', label: 'LLM 模型', icon: <Key size={16} /> },
    { id: 'agent', label: 'Agent 服务', icon: <Server size={16} /> },
    { id: 'rag', label: 'RAG 知识库', icon: <Database size={16} /> },
    { id: 'general', label: '通用设置', icon: <Palette size={16} /> }
  ]

  return (
    <div className="flex h-full overflow-hidden">
      {/* 左侧 Tab 导航 */}
      <div className="w-48 bg-gray-50 border-r border-gray-200 p-4">
        <h2 className="text-lg font-bold text-gray-800 mb-4">设置</h2>
        <nav className="space-y-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
                activeTab === tab.id
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 右侧内容区 */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl">
          {activeTab === 'llm' && <LLMSettings settings={settings} updateSettings={updateSettings} />}
          {activeTab === 'agent' && <AgentSettings settings={settings} updateSettings={updateSettings} />}
          {activeTab === 'rag' && <RAGSettings settings={settings} updateSettings={updateSettings} />}
          {activeTab === 'general' && <GeneralSettings settings={settings} updateSettings={updateSettings} />}

          {/* 保存按钮 */}
          <div className="mt-8 pt-6 border-t border-gray-200">
            <button
              onClick={handleSave}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                saved
                  ? 'bg-green-500 text-white'
                  : 'bg-primary-500 text-white hover:bg-primary-600'
              }`}
            >
              {saved ? <Check size={16} /> : <Save size={16} />}
              {saved ? '已保存' : '保存设置'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// LLM 设置
function LLMSettings({ settings, updateSettings }: SettingsProps) {
  return (
    <div className="space-y-6">
      <SectionTitle title="LLM 模式" description="选择如何连接大语言模型" />

      {/* 模式选择 */}
      <div className="grid grid-cols-2 gap-3">
        <ModeCard
          active={settings.llmMode === 'user_key'}
          onClick={() => updateSettings({ llmMode: 'user_key' })}
          icon={<Key size={20} />}
          title="自有 API Key"
          description="使用你自己的 OpenAI / Anthropic Key"
        />
        <ModeCard
          active={settings.llmMode === 'proxy'}
          onClick={() => updateSettings({ llmMode: 'proxy' })}
          icon={<Server size={20} />}
          title="统一代理"
          description="通过代理服务器转发请求"
        />
      </div>

      {/* 自有 Key 配置 */}
      {settings.llmMode === 'user_key' && (
        <div className="space-y-4 mt-4">
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

      {/* 代理配置 */}
      {settings.llmMode === 'proxy' && (
        <div className="space-y-4 mt-4">
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

      {/* 默认模型 */}
      <div className="mt-6">
        <SectionTitle title="默认模型" description="对话时使用的默认模型" />
        <select
          value={settings.defaultModel}
          onChange={(e) => updateSettings({ defaultModel: e.target.value })}
          className="mt-2 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <optgroup label="OpenAI">
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4o-mini">GPT-4o-mini</option>
            <option value="gpt-4">GPT-4</option>
          </optgroup>
          <optgroup label="Anthropic">
            <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
            <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
            <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
          </optgroup>
        </select>
      </div>
    </div>
  )
}

// Agent 设置
function AgentSettings({ settings, updateSettings }: SettingsProps) {
  return (
    <div className="space-y-6">
      <SectionTitle title="Agent 服务" description="配置 Agent 的运行方式" />

      {/* 模式选择 */}
      <div className="grid grid-cols-2 gap-3">
        <ModeCard
          active={settings.agentMode === 'local'}
          onClick={() => updateSettings({ agentMode: 'local' })}
          icon={<WifiOff size={20} />}
          title="本地运行"
          description="启动本地 Python Agent 进程"
        />
        <ModeCard
          active={settings.agentMode === 'remote'}
          onClick={() => updateSettings({ agentMode: 'remote' })}
          icon={<Wifi size={20} />}
          title="远程服务"
          description="连接远程 Agent API 服务器"
        />
      </div>

      {/* 本地配置 */}
      {settings.agentMode === 'local' && (
        <div className="space-y-4 mt-4">
          <TextInput
            label="本地端口"
            value={String(settings.agentLocalPort)}
            onChange={(v) => updateSettings({ agentLocalPort: parseInt(v) || 8765 })}
            placeholder="8765"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.electronAPI?.agent.start(settings.agentLocalPort)}
              className="px-3 py-1.5 text-sm bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors"
            >
              启动 Agent
            </button>
            <button
              onClick={() => window.electronAPI?.agent.stop()}
              className="px-3 py-1.5 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
            >
              停止 Agent
            </button>
          </div>
          <p className="text-xs text-gray-400">
            本地模式需要 Python 3.10+ 环境，Agent 将在 127.0.0.1:{settings.agentLocalPort} 运行
          </p>
        </div>
      )}

      {/* 远程配置 */}
      {settings.agentMode === 'remote' && (
        <div className="space-y-4 mt-4">
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

// RAG 设置
function RAGSettings({ settings, updateSettings }: SettingsProps) {
  return (
    <div className="space-y-6">
      <SectionTitle title="RAG 知识库" description="配置远程 RAG 检索服务" />

      <TextInput
        label="RAG 服务地址"
        value={settings.ragUrl}
        onChange={(v) => updateSettings({ ragUrl: v })}
        placeholder="https://rag.your-server.com"
      />

      <PasswordInput
        label="RAG API Key"
        value={settings.ragKey}
        onChange={(v) => updateSettings({ ragKey: v })}
        placeholder="输入 RAG 服务的 Key"
      />

      <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
        <p className="text-sm text-blue-700">
          RAG 服务部署在远程服务器，Agent 会在需要时自动调用知识库检索。
          请确保 RAG 服务地址和 Key 配置正确。
        </p>
      </div>
    </div>
  )
}

// 通用设置
function GeneralSettings({ settings, updateSettings }: SettingsProps) {
  return (
    <div className="space-y-6">
      <SectionTitle title="外观" description="自定义应用外观" />

      <div>
        <label className="text-sm font-medium text-gray-700 mb-2 block">主题</label>
        <div className="grid grid-cols-2 gap-3">
          <ModeCard
            active={settings.theme === 'light'}
            onClick={() => updateSettings({ theme: 'light' })}
            icon={<span className="text-xl">☀️</span>}
            title="浅色"
            description="明亮的界面风格"
          />
          <ModeCard
            active={settings.theme === 'dark'}
            onClick={() => updateSettings({ theme: 'dark' })}
            icon={<span className="text-xl">🌙</span>}
            title="深色"
            description="护眼暗色主题"
          />
        </div>
      </div>

      <div className="mt-8">
        <SectionTitle title="关于" description="" />
        <div className="p-4 bg-gray-50 rounded-lg space-y-1">
          <p className="text-sm text-gray-600"><strong>Agent Desktop</strong> v0.1.0</p>
          <p className="text-sm text-gray-500">基于 Electron + React 构建</p>
          <p className="text-sm text-gray-500">Agent 框架版本: v0.2.0</p>
        </div>
      </div>
    </div>
  )
}

// --- 通用子组件 ---

interface SettingsProps {
  settings: Settings
  updateSettings: (partial: Partial<Settings>) => void
}

function SectionTitle({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h3 className="text-base font-semibold text-gray-800">{title}</h3>
      {description && <p className="text-sm text-gray-500 mt-0.5">{description}</p>}
    </div>
  )
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
          ? 'border-primary-500 bg-primary-50'
          : 'border-gray-200 hover:border-gray-300 bg-white'
      }`}
    >
      <div className={`mb-2 ${active ? 'text-primary-600' : 'text-gray-400'}`}>{icon}</div>
      <p className={`text-sm font-medium ${active ? 'text-primary-700' : 'text-gray-700'}`}>
        {title}
      </p>
      <p className="text-xs text-gray-500 mt-0.5">{description}</p>
    </button>
  )
}

function TextInput({
  label,
  value,
  onChange,
  placeholder
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  return (
    <div>
      <label className="text-sm font-medium text-gray-700 mb-1 block">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
      />
    </div>
  )
}

function PasswordInput({
  label,
  value,
  onChange,
  placeholder
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  const [visible, setVisible] = useState(false)

  return (
    <div>
      <label className="text-sm font-medium text-gray-700 mb-1 block">{label}</label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full px-3 py-2 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  )
}
