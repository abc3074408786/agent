import { useState } from 'react'
import { X, FolderOpen, ChevronDown, Check } from 'lucide-react'

interface CreateTeamModalProps {
  onClose: () => void
  onCreate: (team: TeamFormData) => void
}

export interface TeamFormData {
  name: string
  description: string
  leader: TeamMember
  members: TeamMember[]
  project?: string
}

export interface TeamMember {
  agentId: string
  agentName: string
  icon: string
  model: string
  role: 'leader' | 'member'
}

const availableAgents = [
  { id: 'coordinator', name: '协调者 (Coordinator)', icon: '🎯' },
  { id: 'python_developer', name: 'Python 开发', icon: '🐍' },
  { id: 'frontend_developer', name: '前端开发', icon: '🎨' },
  { id: 'test_engineer', name: '测试工程师', icon: '🧪' },
  { id: 'code_reviewer', name: '代码审查', icon: '🔍' },
  { id: 'security_auditor', name: '安全审计', icon: '🛡️' },
  { id: 'architect', name: '架构师', icon: '🏗️' },
  { id: 'devops_agent', name: 'DevOps', icon: '🚀' },
  { id: 'bug_fixer', name: 'Bug 修复', icon: '🐛' },
  { id: 'data_analyst', name: '数据分析', icon: '📊' },
  { id: 'agentic_rag', name: 'RAG 知识库', icon: '📚' },
]

const availableModels = ['gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4', 'claude-3.5-sonnet', 'deepseek-v3', 'qwen-max']

interface TeamTemplate {
  id: string
  name: string
  description: string
  icon: string
  leader: string
  members: string[]
}

const teamTemplates: TeamTemplate[] = [
  { id: 'quick_dev', name: '快速开发', description: '小功能、快速迭代', icon: '⚡', leader: 'coordinator', members: ['python_developer', 'test_engineer'] },
  { id: 'standard_dev', name: '标准开发', description: '正常开发流程，含审查和安全', icon: '🏢', leader: 'coordinator', members: ['python_developer', 'test_engineer', 'code_reviewer', 'security_auditor'] },
  { id: 'architecture', name: '架构设计', description: '新项目设计或大型重构', icon: '🏗️', leader: 'architect', members: ['python_developer', 'frontend_developer', 'devops_agent'] },
  { id: 'bug_fix', name: 'Bug 修复', description: '线上问题定位和修复', icon: '🐛', leader: 'coordinator', members: ['bug_fixer', 'test_engineer'] },
  { id: 'full_stack', name: '全栈项目', description: '大型项目，前后端 + DevOps', icon: '🌐', leader: 'coordinator', members: ['python_developer', 'frontend_developer', 'devops_agent', 'test_engineer', 'code_reviewer'] },
]

export default function CreateTeamModal({ onClose, onCreate }: CreateTeamModalProps) {
  const [step, setStep] = useState<'template' | 'custom'>('template')
  const [teamName, setTeamName] = useState('')
  const [teamDescription, setTeamDescription] = useState('')
  const [selectedLeader, setSelectedLeader] = useState('')
  const [leaderModel, setLeaderModel] = useState('gpt-4o')
  const [selectedMembers, setSelectedMembers] = useState<Map<string, string>>(new Map())
  const [selectedProject, setSelectedProject] = useState('')

  const applyTemplate = (template: TeamTemplate) => {
    setTeamName(template.name + ' 团队')
    setTeamDescription(template.description)
    setSelectedLeader(template.leader)
    setLeaderModel('gpt-4o')
    const members = new Map<string, string>()
    template.members.forEach(id => members.set(id, 'gpt-4o'))
    setSelectedMembers(members)
    setStep('custom')
  }

  const toggleMember = (agentId: string) => {
    const next = new Map(selectedMembers)
    if (next.has(agentId)) next.delete(agentId)
    else next.set(agentId, 'gpt-4o')
    setSelectedMembers(next)
  }

  const setMemberModel = (agentId: string, model: string) => {
    const next = new Map(selectedMembers)
    next.set(agentId, model)
    setSelectedMembers(next)
  }

  const handleCreate = () => {
    if (!teamName.trim() || !selectedLeader) return
    const leaderAgent = availableAgents.find(a => a.id === selectedLeader)!
    const members: TeamMember[] = Array.from(selectedMembers.entries()).map(([agentId, model]) => {
      const agent = availableAgents.find(a => a.id === agentId)!
      return { agentId, agentName: agent.name, icon: agent.icon, model, role: 'member' as const }
    })
    onCreate({
      name: teamName.trim(),
      description: teamDescription.trim(),
      leader: { agentId: selectedLeader, agentName: leaderAgent.name, icon: leaderAgent.icon, model: leaderModel, role: 'leader' },
      members,
      project: selectedProject || undefined
    })
  }

  const canCreate = teamName.trim() && selectedLeader && selectedMembers.size > 0
  const memberOptions = availableAgents.filter(a => a.id !== selectedLeader)

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-[580px] max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-6 pb-4">
          <h3 className="text-lg font-bold text-gray-800">创建团队</h3>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          {step === 'template' ? (
            <div>
              <p className="text-sm text-gray-500 mb-4">选择一个预设模板快速开始，或自定义配置</p>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {teamTemplates.map((tpl) => (
                  <button key={tpl.id} onClick={() => applyTemplate(tpl)} className="flex items-start gap-3 p-4 border border-gray-150 rounded-xl hover:border-blue-300 hover:bg-blue-50/30 transition-all text-left group">
                    <span className="text-2xl">{tpl.icon}</span>
                    <div>
                      <p className="text-sm font-medium text-gray-800 group-hover:text-blue-600">{tpl.name}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{tpl.description}</p>
                      <p className="text-xs text-gray-400 mt-1">{tpl.members.length + 1} 个 Agent</p>
                    </div>
                  </button>
                ))}
              </div>
              <button onClick={() => setStep('custom')} className="w-full py-3 text-sm text-gray-600 border border-dashed border-gray-300 rounded-xl hover:border-blue-400 hover:text-blue-600 transition-colors">+ 从零开始自定义</button>
            </div>
          ) : (
            <div className="space-y-5">
              <button onClick={() => setStep('template')} className="text-xs text-blue-500 hover:text-blue-700 transition-colors">← 返回模板选择</button>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-1.5 block">团队名称 <span className="text-red-500">*</span></label>
                <input type="text" value={teamName} onChange={(e) => setTeamName(e.target.value)} placeholder="例如：全栈开发组" className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-1.5 block">团队描述</label>
                <input type="text" value={teamDescription} onChange={(e) => setTeamDescription(e.target.value)} placeholder="这个团队负责什么工作" className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">团队 Leader <span className="text-red-500">*</span></label>
                <p className="text-xs text-gray-400 mb-3">负责拆解任务并协调团队工作</p>
                <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-50 max-h-[180px] overflow-y-auto">
                  {availableAgents.map((agent) => (
                    <div key={agent.id} className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${selectedLeader === agent.id ? 'bg-blue-50' : 'hover:bg-gray-50'}`} onClick={() => setSelectedLeader(agent.id)}>
                      <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${selectedLeader === agent.id ? 'border-blue-500' : 'border-gray-300'}`}>
                        {selectedLeader === agent.id && <div className="w-2 h-2 rounded-full bg-blue-500" />}
                      </div>
                      <span className="text-base">{agent.icon}</span>
                      <span className="flex-1 text-sm text-gray-700">{agent.name}</span>
                      {selectedLeader === agent.id && (
                        <select value={leaderModel} onChange={(e) => setLeaderModel(e.target.value)} onClick={(e) => e.stopPropagation()} className="px-2 py-1 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white">
                          {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">团队成员 <span className="text-red-500">*</span><span className="text-gray-400 font-normal ml-2">已选 {selectedMembers.size} 个</span></label>
                <p className="text-xs text-gray-400 mb-3">执行具体子任务的 Agent（可多选）</p>
                <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-50 max-h-[220px] overflow-y-auto">
                  {memberOptions.map((agent) => {
                    const isSelected = selectedMembers.has(agent.id)
                    return (
                      <div key={agent.id} className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${isSelected ? 'bg-green-50/50' : 'hover:bg-gray-50'}`} onClick={() => toggleMember(agent.id)}>
                        <div className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 ${isSelected ? 'border-blue-500 bg-blue-500' : 'border-gray-300'}`}>
                          {isSelected && <Check size={10} className="text-white" />}
                        </div>
                        <span className="text-base">{agent.icon}</span>
                        <span className="flex-1 text-sm text-gray-700">{agent.name}</span>
                        {isSelected && (
                          <select value={selectedMembers.get(agent.id) || 'gpt-4o'} onChange={(e) => setMemberModel(agent.id, e.target.value)} onClick={(e) => e.stopPropagation()} className="px-2 py-1 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white">
                            {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                          </select>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-1.5 block">项目 <span className="text-gray-400 font-normal">（可选）</span></label>
                <button className="w-full flex items-center gap-2 px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-500 hover:border-gray-300 transition-colors">
                  <FolderOpen size={15} className="text-gray-400" />
                  <span className="flex-1 text-left">{selectedProject || '选择项目文件夹'}</span>
                  <ChevronDown size={14} className="text-gray-400" />
                </button>
              </div>
            </div>
          )}
        </div>

        {step === 'custom' && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
            <div className="text-xs text-gray-400">{selectedLeader && `Leader + ${selectedMembers.size} 成员`}</div>
            <div className="flex items-center gap-3">
              <button onClick={onClose} className="px-5 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">取消</button>
              <button onClick={handleCreate} disabled={!canCreate} className={`px-5 py-2 text-sm font-medium rounded-lg transition-colors ${canCreate ? 'bg-blue-500 text-white hover:bg-blue-600' : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}>创建团队</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
