import { useState } from 'react'
import {
  ChevronDown, ChevronRight, CheckCircle2, Loader2, XCircle,
  FileText, Terminal, GitBranch, Search, Globe, Calculator
} from 'lucide-react'
import { ToolCall } from '../store'

interface ToolCallViewProps {
  toolCalls: ToolCall[]
}

// Map tool names to icons
const toolIcons: Record<string, React.ReactNode> = {
  file_read: <FileText size={13} />,
  file_write: <FileText size={13} />,
  file_edit: <FileText size={13} />,
  bash_execute: <Terminal size={13} />,
  git_status: <GitBranch size={13} />,
  git_diff: <GitBranch size={13} />,
  git_commit: <GitBranch size={13} />,
  git_log: <GitBranch size={13} />,
  grep_search: <Search size={13} />,
  glob_search: <Search size={13} />,
  web_search: <Globe size={13} />,
  http_request: <Globe size={13} />,
  calculator: <Calculator size={13} />,
}

const statusIcons = {
  running: <Loader2 size={13} className="text-accent-blue animate-spin" />,
  completed: <CheckCircle2 size={13} className="text-accent-green" />,
  failed: <XCircle size={13} className="text-accent-red" />,
}

export default function ToolCallView({ toolCalls }: ToolCallViewProps) {
  if (!toolCalls || toolCalls.length === 0) return null

  return (
    <div className="space-y-1.5 my-2">
      {toolCalls.map((tc) => (
        <ToolCallItem key={tc.id} toolCall={tc} />
      ))}
    </div>
  )
}

function ToolCallItem({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false)

  const icon = toolIcons[toolCall.name] || <Terminal size={13} />
  const duration = toolCall.durationMs ? `${(toolCall.durationMs / 1000).toFixed(1)}s` : null

  // Format args for display
  const argsPreview = Object.entries(toolCall.args || {})
    .slice(0, 2)
    .map(([k, v]) => {
      const val = typeof v === 'string' ? (v.length > 40 ? v.slice(0, 40) + '...' : v) : JSON.stringify(v)
      return `${k}: ${val}`
    })
    .join(', ')

  return (
    <div
      className="rounded-lg border border-border overflow-hidden transition-all"
      style={{ background: 'var(--surface-secondary)' }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface-tertiary transition-colors"
      >
        {/* Expand toggle */}
        <span className="text-text-tertiary shrink-0">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>

        {/* Tool icon */}
        <span className="text-text-secondary shrink-0">{icon}</span>

        {/* Tool name */}
        <span className="text-xs font-mono font-medium text-text-primary">{toolCall.name}</span>

        {/* Args preview */}
        {argsPreview && !expanded && (
          <span className="text-[11px] text-text-tertiary truncate flex-1">
            {argsPreview}
          </span>
        )}

        {/* Right side: status + duration */}
        <div className="flex items-center gap-2 shrink-0 ml-auto">
          {duration && (
            <span className="text-[10px] text-text-tertiary font-mono">{duration}</span>
          )}
          {statusIcons[toolCall.status]}
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-border">
          {/* Args */}
          {Object.keys(toolCall.args || {}).length > 0 && (
            <div className="mt-2">
              <p className="text-[10px] text-text-tertiary uppercase tracking-wider mb-1">参数</p>
              <pre className="text-[11px] font-mono text-text-secondary bg-surface-tertiary rounded-md p-2 overflow-x-auto max-h-[120px]">
                {JSON.stringify(toolCall.args, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {toolCall.result && (
            <div className="mt-2">
              <p className="text-[10px] text-text-tertiary uppercase tracking-wider mb-1">结果</p>
              <pre className="text-[11px] font-mono text-text-secondary bg-surface-tertiary rounded-md p-2 overflow-x-auto max-h-[200px] whitespace-pre-wrap">
                {toolCall.result.length > 500 ? toolCall.result.slice(0, 500) + '\n...(截断)' : toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
