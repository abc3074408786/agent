import { useState } from 'react'
import { X, FolderOpen, ChevronDown } from 'lucide-react'

interface CreateTeamModalProps {
  onClose: () => void
  onCreate: (team: { name: string; leader: string; project?: string }) => void
}

// 可选的 Leader Agent 列表
const leaderOptions = [
  { id: 'agent_cli', name: 'Agent CLI', icon: '⊙' },
  { id: 'claude_code', name: 'Claude Code', icon: '🌸' },
  { id: 'codex_cli', name: 'Codex CLI', icon: '⊙' },
  { id: 'gemini_cli', name: 'Gemini CLI', icon: '✦' },
  { id: 'rag_agent', name: 'RAG Agent', icon: '📚' },
  { id: 'cowork', name: 'Cowork', icon: '⚡' },
  { id: 'python_dev', name: 'Python Developer', icon: '🐍' },
  { id: 'code_reviewer', name: 'Code Reviewer', icon: '🔍' },
]

export default function CreateTeamModal({ onClose, onCreate }: CreateTeamModalProps) {
  const [teamName, setTeamName] = useState('')
  const [selectedLeader, setSelectedLeader] = useState('')
  const [selectedProject, setSelectedProject] = useState('')

  const handleCreate = () => {
    if (!teamName.trim() || !selectedLeader) return
    onCreate({
      name: teamName.trim(),
      leader: selectedLeader,
      project: selectedProject || undefined
    })
  }

  const canCreate = teamName.trim() && selectedLeader

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-[480px] max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4">
          <h3 className="text-lg font-bold text-gray-800">创建团队</h3>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-5">
          {/* 团队名称 */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1.5 block">
              团队名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="团队名称"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* 团队 Leader */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">
              团队 Leader <span className="text-red-500">*</span>
            </label>
            <p className="text-xs text-gray-400 mb-3">
              接收你的指令，拆解任务并分配给团队中的 Agent
            </p>

            {/* Radio 列表 */}
            <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100 max-h-[280px] overflow-y-auto">
              {leaderOptions.map((option) => (
                <label
                  key={option.id}
                  className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                    selectedLeader === option.id
                      ? 'bg-blue-50'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  {/* Radio 圆圈 */}
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${
                    selectedLeader === option.id
                      ? 'border-blue-500'
                      : 'border-gray-300'
                  }`}>
                    {selectedLeader === option.id && (
                      <div className="w-2 h-2 rounded-full bg-blue-500" />
                    )}
                  </div>

                  {/* 图标 */}
                  <span className="text-lg">{option.icon}</span>

                  {/* 名称 */}
                  <span className="text-sm text-gray-700">{option.name}</span>

                  {/* 隐藏的 input */}
                  <input
                    type="radio"
                    name="leader"
                    value={option.id}
                    checked={selectedLeader === option.id}
                    onChange={() => setSelectedLeader(option.id)}
                    className="sr-only"
                  />
                </label>
              ))}
            </div>
          </div>

          {/* 项目选择（可选） */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1.5 block">
              项目 <span className="text-gray-400 font-normal">（可选）</span>
            </label>
            <button
              className="w-full flex items-center gap-2 px-3 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-500 hover:border-gray-300 transition-colors"
            >
              <FolderOpen size={15} className="text-gray-400" />
              <span className="flex-1 text-left">
                {selectedProject || '选择项目文件夹'}
              </span>
              <ChevronDown size={14} className="text-gray-400" />
            </button>
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100">
          <button
            onClick={onClose}
            className="px-5 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleCreate}
            disabled={!canCreate}
            className={`px-5 py-2 text-sm font-medium rounded-lg transition-colors ${
              canCreate
                ? 'bg-blue-500 text-white hover:bg-blue-600'
                : 'bg-blue-200 text-white cursor-not-allowed'
            }`}
          >
            创建团队
          </button>
        </div>
      </div>
    </div>
  )
}
