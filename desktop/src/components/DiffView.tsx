import { useState } from 'react'
import { FileText, ChevronDown, ChevronRight, Plus, Minus, Copy, Check } from 'lucide-react'

export interface DiffFile {
  filename: string
  status: 'added' | 'modified' | 'deleted'
  hunks: DiffHunk[]
}

export interface DiffHunk {
  oldStart: number
  newStart: number
  lines: DiffLine[]
}

export interface DiffLine {
  type: 'add' | 'remove' | 'context'
  content: string
  oldLineNo?: number
  newLineNo?: number
}

interface DiffViewProps {
  files: DiffFile[]
  title?: string
}

export default function DiffView({ files, title }: DiffViewProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(
    new Set(files.map(f => f.filename))
  )

  const toggleFile = (filename: string) => {
    const next = new Set(expandedFiles)
    if (next.has(filename)) {
      next.delete(filename)
    } else {
      next.add(filename)
    }
    setExpandedFiles(next)
  }

  const stats = files.reduce(
    (acc, f) => {
      f.hunks.forEach(h => {
        h.lines.forEach(l => {
          if (l.type === 'add') acc.additions++
          if (l.type === 'remove') acc.deletions++
        })
      })
      return acc
    },
    { additions: 0, deletions: 0 }
  )

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-gray-500" />
          <span className="text-sm font-medium text-gray-700">
            {title || '代码变更'}
          </span>
          <span className="text-xs text-gray-400">
            {files.length} 个文件
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green-600 font-medium">+{stats.additions}</span>
          <span className="text-red-500 font-medium">-{stats.deletions}</span>
        </div>
      </div>

      {/* File list */}
      <div className="divide-y divide-gray-100">
        {files.map((file) => (
          <div key={file.filename}>
            {/* File header */}
            <button
              onClick={() => toggleFile(file.filename)}
              className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-gray-50 transition-colors"
            >
              {expandedFiles.has(file.filename) ? (
                <ChevronDown size={14} className="text-gray-400" />
              ) : (
                <ChevronRight size={14} className="text-gray-400" />
              )}
              <FileStatusBadge status={file.status} />
              <span className="text-sm text-gray-700 font-mono truncate">
                {file.filename}
              </span>
            </button>

            {/* Diff content */}
            {expandedFiles.has(file.filename) && (
              <div className="bg-gray-50/50 overflow-x-auto">
                {file.hunks.map((hunk, hunkIdx) => (
                  <div key={hunkIdx} className="border-t border-gray-100">
                    {/* Hunk header */}
                    <div className="px-4 py-1 bg-blue-50/50 text-xs text-blue-600 font-mono">
                      @@ -{hunk.oldStart} +{hunk.newStart} @@
                    </div>
                    {/* Lines */}
                    <div className="font-mono text-xs leading-5">
                      {hunk.lines.map((line, lineIdx) => (
                        <DiffLineRow key={lineIdx} line={line} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function DiffLineRow({ line }: { line: DiffLine }) {
  const bgClass =
    line.type === 'add'
      ? 'bg-green-50'
      : line.type === 'remove'
      ? 'bg-red-50'
      : ''

  const textClass =
    line.type === 'add'
      ? 'text-green-800'
      : line.type === 'remove'
      ? 'text-red-800'
      : 'text-gray-600'

  const prefix =
    line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' '

  return (
    <div className={`flex ${bgClass} hover:brightness-95 transition-all`}>
      {/* Old line number */}
      <span className="w-10 shrink-0 text-right pr-2 text-gray-400 select-none border-r border-gray-200 bg-gray-50/80">
        {line.type !== 'add' ? line.oldLineNo : ''}
      </span>
      {/* New line number */}
      <span className="w-10 shrink-0 text-right pr-2 text-gray-400 select-none border-r border-gray-200 bg-gray-50/80">
        {line.type !== 'remove' ? line.newLineNo : ''}
      </span>
      {/* Prefix */}
      <span className={`w-5 shrink-0 text-center select-none ${textClass} font-bold`}>
        {prefix}
      </span>
      {/* Content */}
      <span className={`flex-1 px-2 whitespace-pre ${textClass}`}>
        {line.content}
      </span>
    </div>
  )
}

function FileStatusBadge({ status }: { status: 'added' | 'modified' | 'deleted' }) {
  const config = {
    added: { label: 'A', bg: 'bg-green-100 text-green-700' },
    modified: { label: 'M', bg: 'bg-yellow-100 text-yellow-700' },
    deleted: { label: 'D', bg: 'bg-red-100 text-red-700' }
  }
  const { label, bg } = config[status]
  return (
    <span className={`w-5 h-5 rounded text-xs font-bold flex items-center justify-center ${bg}`}>
      {label}
    </span>
  )
}

// 辅助函数：将 unified diff 文本解析为 DiffFile 数组
export function parseDiffText(diffText: string): DiffFile[] {
  const files: DiffFile[] = []
  const fileBlocks = diffText.split(/^diff --git/m).filter(Boolean)

  for (const block of fileBlocks) {
    const lines = block.split('\n')
    const filenameLine = lines[0]
    const match = filenameLine.match(/b\/(.+)$/)
    const filename = match ? match[1] : 'unknown'

    let status: 'added' | 'modified' | 'deleted' = 'modified'
    if (block.includes('new file mode')) status = 'added'
    if (block.includes('deleted file mode')) status = 'deleted'

    const hunks: DiffHunk[] = []
    let currentHunk: DiffHunk | null = null
    let oldLine = 0
    let newLine = 0

    for (const line of lines) {
      const hunkMatch = line.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/)
      if (hunkMatch) {
        oldLine = parseInt(hunkMatch[1])
        newLine = parseInt(hunkMatch[2])
        currentHunk = { oldStart: oldLine, newStart: newLine, lines: [] }
        hunks.push(currentHunk)
        continue
      }

      if (!currentHunk) continue

      if (line.startsWith('+')) {
        currentHunk.lines.push({
          type: 'add',
          content: line.slice(1),
          newLineNo: newLine++
        })
      } else if (line.startsWith('-')) {
        currentHunk.lines.push({
          type: 'remove',
          content: line.slice(1),
          oldLineNo: oldLine++
        })
      } else if (line.startsWith(' ')) {
        currentHunk.lines.push({
          type: 'context',
          content: line.slice(1),
          oldLineNo: oldLine++,
          newLineNo: newLine++
        })
      }
    }

    files.push({ filename, status, hunks })
  }

  return files
}
