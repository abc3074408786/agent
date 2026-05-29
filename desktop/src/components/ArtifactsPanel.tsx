import { useState } from 'react'
import { X, Copy, Check, FileCode, ChevronDown, ChevronRight, Download } from 'lucide-react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useAppStore, Artifact } from '../store'

export default function ArtifactsPanel() {
  const { settings, toggleArtifactsPanel, sessions, currentSessionId } = useAppStore()

  if (!settings.artifactsPanelOpen) return null

  const session = sessions.find((s) => s.id === currentSessionId)
  const artifacts = session?.artifacts || []

  return (
    <div
      className="w-[420px] h-full border-l border-border flex flex-col animate-slide-in-right"
      style={{ background: 'var(--surface-primary)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <FileCode size={16} className="text-primary-500" />
          <h3 className="text-sm font-semibold text-text-primary">Artifacts</h3>
          <span className="text-[10px] text-text-tertiary bg-surface-tertiary px-1.5 py-0.5 rounded-full">
            {artifacts.length}
          </span>
        </div>
        <button
          onClick={toggleArtifactsPanel}
          className="p-1.5 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {artifacts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
            <FileCode size={40} className="mb-3 opacity-30" />
            <p className="text-sm">暂无生成文件</p>
            <p className="text-xs mt-1 opacity-60">Agent 生成的文件会在此显示</p>
          </div>
        ) : (
          <div className="py-2">
            {artifacts.map((artifact) => (
              <ArtifactItem key={artifact.id} artifact={artifact} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ArtifactItem({ artifact }: { artifact: Artifact }) {
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(artifact.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([artifact.content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = artifact.filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-3 mb-3 rounded-xl border border-border overflow-hidden" style={{ background: 'var(--surface-secondary)' }}>
      {/* File header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-text-tertiary shrink-0"
        >
          {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>
        <FileCode size={13} className="text-primary-400 shrink-0" />
        <span className="text-xs font-mono font-medium text-text-primary flex-1 truncate">
          {artifact.filename}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="p-1 text-text-tertiary hover:text-text-primary rounded transition-colors"
            title="复制"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
          <button
            onClick={handleDownload}
            className="p-1 text-text-tertiary hover:text-text-primary rounded transition-colors"
            title="下载"
          >
            <Download size={12} />
          </button>
        </div>
      </div>

      {/* Code */}
      {expanded && (
        <div className="max-h-[400px] overflow-auto">
          <SyntaxHighlighter
            language={artifact.language || 'text'}
            style={oneDark}
            customStyle={{
              margin: 0,
              borderRadius: 0,
              padding: '12px 16px',
              fontSize: '12px',
              background: 'var(--code-bg)',
            }}
          >
            {artifact.content}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  )
}
