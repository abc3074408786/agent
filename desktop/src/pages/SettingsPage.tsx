import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Eye, EyeOff, Plus, Minus, Pencil, ChevronRight, ChevronDown,
  ToggleLeft, ToggleRight, ArrowLeft, Moon, Sun, Monitor,
  Bot, Cpu, Users, Zap, Globe, PawPrint, Layers, Info, Check
} from 'lucide-react'
import { useAppStore, Settings } from '../store'

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

const localAgents = [
  { id: 'agent_cli', name: 'Agent CLI', icon: '⊙', detected: true },
  { id: 'claude_code', name: 'Claude Code', icon: '🌸', detected: true },
  { id: 'codex_cli', name: 'Codex CLI', icon: '⊙', detected: true },
  { id: 'gemini_cli', name: 'Gemini CLI', icon: '✦', detected: true },
  { id: 'rag_agent', name: 'RAG Agent', icon: '📚', detected: true },
]

export default function SettingsPage() {
  const { settings, updateSettings } = useAppStore()
  const [activeSection, setActiveSection] = useState<SettingsSection>('agents')
  const navigate = useNavigate()

  return (
    <div className="flex h-full overflow-hidden" style={{ background: 'var(--surface-primary)' }}>
      {/* Left nav */}
      <div className="w-[200px] h-full border-r border-border flex flex-col" style={{ background: 'var(--surface-secondary)' }}>
        <nav className="flex-1 overflow-y-auto px-3 pt-4 pb-4">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-3 mb-1.5 text-[10px] text-primary-500 font-semibold uppercase tracking-wider">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setActiveSection(item.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-all ${
                      activeSection === item.id
                        ? 'bg-surface-tertiary text-text-primary font-medium'
                        : 'text-text-secondary hover:bg-surface-tertiary'
                    }`}
                  >
                    <span className={activeSection === item.id ? 'text-text-primary' : 'text-text-tertiary'}>
                      {item.icon}
                    </span>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="px-3 py-3 border-t border-border flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors"
          >
            <ArrowLeft size={14} />
            返回
          </button>
        </div>
      </div>

      {/* Right content */}
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

// ============ Agents ============
function AgentsSection() {
  const navigate = useNavigate()
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">本地 Agents</h3>
      <div className="mb-6 px-4 py-3 rounded-lg" style={{ background: 'var(--surface-tertiary)' }}>
        <p className="text-sm text-text-secondary">
          Agent CLI 是内置 Agent，App 自带无需安装；其他 Agent 需先在本地安装对应 CLI 才能被识别。
        </p>
      </div>
      <p className="text-sm text-text-secondary mb-4">已检测</p>
      <div className="grid grid-cols-5 gap-4">
        {localAgents.map((agent) => (
          <div
            key={agent.id}
            className="flex flex-col items-center p-5 rounded-xl border border-border hover:border-primary-300 hover:shadow-sm transition-all"
            style={{ background: 'var(--surface-secondary)' }}
          >
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-3 text-2xl" style={{ background: 'var(--surface-tertiary)' }}>
              {agent.icon}
            </div>
            <p className="text-sm font-medium text-text-primary mb-1">{agent.name}</p>
            <p className="text-xs text-text-tertiary mb-3">已检测</p>
            <button
              onClick={() => navigate('/')}
              className="w-full py-1.5 text-xs text-text-secondary border border-border rounded-lg hover:bg-surface-tertiary transition-colors"
            >
              开始对话
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============ Models ============
interface SettingsProps {
  settings: Settings
  updateSettings: (partial: Partial<Settings>) => void
}

function ModelsSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">模型</h3>
      <div className="mb-5 px-4 py-3 rounded-lg" style={{ background: 'var(--surface-tertiary)' }}>
        <p className="text-sm text-text-secondary">配置 LLM 提供商和 API Key。</p>
      </div>

      <div className="space-y-4">
        <div className="p-5 rounded-xl border border-border" style={{ background: 'var(--surface-secondary)' }}>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xl">●</span>
            <div>
              <p className="text-sm font-semibold text-text-primary">OpenAI</p>
              <p className="text-xs text-text-tertiary">GPT-4o, GPT-4o Mini, GPT-4 Turbo</p>
            </div>
          </div>
          <PasswordInput label="API Key" value={settings.openaiKey} onChange={(v) => updateSettings({ openaiKey: v })} placeholder="sk-..." />
        </div>

        <div className="p-5 rounded-xl border border-border" style={{ background: 'var(--surface-secondary)' }}>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xl">◈</span>
            <div>
              <p className="text-sm font-semibold text-text-primary">Anthropic</p>
              <p className="text-xs text-text-tertiary">Claude Sonnet 4, Claude 3.5 Sonnet/Haiku</p>
            </div>
          </div>
          <PasswordInput label="API Key" value={settings.anthropicKey} onChange={(v) => updateSettings({ anthropicKey: v })} placeholder="sk-ant-..." />
        </div>
      </div>
    </div>
  )
}

// ============ Assistants ============
function AssistantsSection() {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">助手</h3>
      <div className="px-4 py-3 rounded-lg" style={{ background: 'var(--surface-tertiary)' }}>
        <p className="text-sm text-text-secondary">管理可用的 Agent 助手预设，支持自定义 Prompt 和工具配置。</p>
      </div>
    </div>
  )
}

// ============ Extensions ============
function ExtensionsSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">能力扩展</h3>
      <div className="space-y-4">
        <div className="p-5 rounded-xl border border-border" style={{ background: 'var(--surface-secondary)' }}>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">📚</span>
            <div>
              <p className="text-sm font-semibold text-text-primary">RAG 知识库</p>
              <p className="text-xs text-text-tertiary">远程检索增强生成服务</p>
            </div>
          </div>
          <div className="space-y-3">
            <TextInput label="服务地址" value={settings.ragUrl} onChange={(v) => updateSettings({ ragUrl: v })} placeholder="https://rag.your-server.com" />
            <PasswordInput label="API Key" value={settings.ragKey} onChange={(v) => updateSettings({ ragKey: v })} placeholder="输入 RAG 服务的 Key" />
          </div>
        </div>

        <div className="p-5 rounded-xl border border-border opacity-50" style={{ background: 'var(--surface-secondary)' }}>
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔌</span>
            <div>
              <p className="text-sm font-semibold text-text-primary">MCP 协议</p>
              <p className="text-xs text-text-tertiary">Model Context Protocol 集成（即将推出）</p>
            </div>
          </div>
        </div>

        {/* Expert Marketplace API */}
        <div className="p-5 rounded-xl border border-border" style={{ background: 'var(--surface-secondary)' }}>
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🛒</span>
            <div>
              <p className="text-sm font-semibold text-text-primary">外部专家市场</p>
              <p className="text-xs text-text-tertiary">对接第三方专家/技能市场 API（如 OmniWork）</p>
            </div>
          </div>
          <div className="space-y-3">
            <TextInput
              label="市场 API 地址"
              value={(settings as any).marketplaceUrl || ''}
              onChange={(v) => updateSettings({ marketplaceUrl: v } as any)}
              placeholder="https://api.omniwork.ai/v1"
            />
            <PasswordInput
              label="API Key（可选）"
              value={(settings as any).marketplaceKey || ''}
              onChange={(v) => updateSettings({ marketplaceKey: v } as any)}
              placeholder="输入市场 API Key"
            />
            <p className="text-[10px] text-text-tertiary leading-relaxed">
              配置后，专家市场会自动从该地址拉取可用专家列表。支持返回格式：
              <code className="px-1 rounded" style={{ background: 'var(--surface-tertiary)' }}>
                {`{ "experts": [{ "id", "name", "description", "icon", "category", "capabilities", "system_prompt" }] }`}
              </code>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============ Display ============
function DisplaySection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">显示</h3>
      <div className="space-y-6">
        <div>
          <p className="text-sm font-medium text-text-primary mb-3">主题</p>
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
            <ThemeOption
              active={settings.theme === 'system'}
              onClick={() => updateSettings({ theme: 'system' })}
              label="跟随系统"
              icon={<Monitor size={18} />}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

// ============ Remote ============
function RemoteSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">远程连接</h3>
      <div className="space-y-4">
        <TextInput label="Agent 服务地址" value={settings.agentRemoteUrl} onChange={(v) => updateSettings({ agentRemoteUrl: v })} placeholder="https://agent.your-server.com" />
        <TextInput label="本地端口" value={String(settings.agentLocalPort)} onChange={(v) => updateSettings({ agentLocalPort: parseInt(v) || 8765 })} placeholder="8765" />

        {/* CLI Agent 选择 */}
        <div className="mt-6 pt-6 border-t border-border">
          <h4 className="text-sm font-semibold text-text-primary mb-3">CLI Agent 集成 (ACP)</h4>
          <p className="text-xs text-text-tertiary mb-4">
            选择一个已安装的 CLI Agent，通过 ACP 协议在界面中调用。需要本地已安装对应工具。
          </p>
          <div className="space-y-2">
            <CliAgentOption
              active={(settings as any).activeCliAgent === 'none'}
              onClick={() => updateSettings({ activeCliAgent: 'none' } as any)}
              icon="⊘"
              name="不使用"
              description="仅使用内置 Agent HTTP API"
            />
            <CliAgentOption
              active={(settings as any).activeCliAgent === 'codex'}
              onClick={() => updateSettings({ activeCliAgent: 'codex' } as any)}
              icon="⊙"
              name="Codex CLI"
              description="OpenAI Codex (需安装 npm i -g @openai/codex)"
            />
            <CliAgentOption
              active={(settings as any).activeCliAgent === 'claude_code'}
              onClick={() => updateSettings({ activeCliAgent: 'claude_code' } as any)}
              icon="🌸"
              name="Claude Code"
              description="Anthropic Claude Code CLI (即将支持)"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function CliAgentOption({ active, onClick, icon, name, description }: {
  active: boolean; onClick: () => void; icon: string; name: string; description: string
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${
        active ? 'border-primary-500 bg-primary-500/5' : 'border-border hover:border-text-tertiary'
      }`}
      style={{ background: active ? undefined : 'var(--surface-secondary)' }}
    >
      <span className="text-lg">{icon}</span>
      <div className="flex-1">
        <p className={`text-sm font-medium ${active ? 'text-primary-500' : 'text-text-primary'}`}>{name}</p>
        <p className="text-[10px] text-text-tertiary">{description}</p>
      </div>
      {active && <Check size={16} className="text-primary-500" />}
    </button>
  )
}

// ============ System ============
function SystemSection({ settings, updateSettings }: SettingsProps) {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">系统</h3>
      <div className="space-y-3">
        <ToggleRow title="开机自启" description="系统启动时自动运行 Agent Desktop" enabled={false} onToggle={() => {}} />
        <ToggleRow title="最小化到托盘" description="关闭窗口时最小化到系统托盘" enabled={true} onToggle={() => {}} />
      </div>
    </div>
  )
}

// ============ About ============
function AboutSection() {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-6">关于</h3>
      <div className="p-6 rounded-xl border border-border" style={{ background: 'var(--surface-secondary)' }}>
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-lg">
            <span className="text-white text-2xl font-bold">A</span>
          </div>
          <div>
            <h4 className="text-lg font-bold text-text-primary">Agent Desktop</h4>
            <p className="text-sm text-text-tertiary">v0.2.0</p>
          </div>
        </div>
        <div className="space-y-2 text-sm">
          <InfoRow label="框架" value="Electron + React + TypeScript" />
          <InfoRow label="Agent 版本" value="v0.2.0" />
          <InfoRow label="内置工具" value="20 个" />
          <InfoRow label="技能包" value="11 个" />
          <InfoRow label="开源协议" value="MIT" />
        </div>
      </div>
    </div>
  )
}

function PlaceholderSection({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h3 className="text-xl font-bold text-text-primary mb-4">{title}</h3>
      <div className="px-4 py-3 rounded-lg" style={{ background: 'var(--surface-tertiary)' }}>
        <p className="text-sm text-text-secondary">{description}</p>
      </div>
    </div>
  )
}

// ============ Shared components ============
function ThemeOption({ active, onClick, label, icon }: { active: boolean; onClick: () => void; label: string; icon: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-3 rounded-xl border-2 transition-all ${
        active ? 'border-primary-500 text-primary-500' : 'border-border text-text-secondary hover:border-text-tertiary'
      }`}
      style={active ? { background: 'rgba(59, 130, 246, 0.05)' } : undefined}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}

function ToggleRow({ title, description, enabled, onToggle }: { title: string; description: string; enabled: boolean; onToggle: () => void }) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl border border-border" style={{ background: 'var(--surface-secondary)' }}>
      <div>
        <p className="text-sm font-medium text-text-primary">{title}</p>
        <p className="text-xs text-text-tertiary">{description}</p>
      </div>
      <button onClick={onToggle} className={enabled ? 'text-primary-500' : 'text-text-tertiary'}>
        {enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
      </button>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-2 border-b border-border">
      <span className="text-text-secondary">{label}</span>
      <span className="text-text-primary font-medium">{value}</span>
    </div>
  )
}

function TextInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div>
      <label className="text-xs font-medium text-text-secondary mb-1 block">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 text-text-primary placeholder-text-tertiary"
        style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
      />
    </div>
  )
}

function PasswordInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  const [visible, setVisible] = useState(false)
  return (
    <div>
      <label className="text-xs font-medium text-text-secondary mb-1 block">{label}</label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full px-3 py-2 pr-10 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 text-text-primary placeholder-text-tertiary"
          style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary"
        >
          {visible ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
    </div>
  )
}
