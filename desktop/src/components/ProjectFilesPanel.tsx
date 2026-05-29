import { useState, useEffect } from 'react'
import {
  X, FolderOpen, File, ChevronDown, ChevronRight, RefreshCw,
  FileCode, FileText, FileImage, FileCog, Search, GitBranch
} from 'lucide-react'
import { useAppStore, FileTreeNode } from '../store'

// File icon mapping by extension
function getFileIcon(name: string): React.ReactNode {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  const codeExts = ['ts', 'tsx', 'js', 'jsx', 'py', 'rs', 'go', 'java', 'c', 'cpp', 'h', 'rb', 'php', 'swift', 'kt']
  const configExts = ['json', 'yaml', 'yml', 'toml', 'ini', 'env', 'cfg']
  const imageExts = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico']

  if (codeExts.includes(ext)) return <FileCode size={14} className="text-primary-400" />
  if (configExts.includes(ext)) return <FileCog size={14} className="text-accent-amber" />
  if (imageExts.includes(ext)) return <FileImage size={14} className="text-accent-green" />
  if (['md', 'txt', 'rst', 'doc'].includes(ext)) return <FileText size={14} className="text-text-tertiary" />
  return <File size={14} className="text-text-tertiary" />
}

export default function ProjectFilesPanel() {
  const {
    projectFilesOpen, toggleProjectFiles,
    projects, currentProjectId, fileTree, setFileTree
  } = useAppStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [activeTab, setActiveTab] = useState<'files' | 'changes'>('files')

  const currentProject = projects.find(p => p.id === currentProjectId)

  // Don't render if not open or no project selected
  if (!projectFilesOpen || !currentProject) return null

  const handleRefresh = async () => {
    try {
      const tree = await window.electronAPI?.project?.readDir(currentProject.path)
      if (tree) setFileTree(tree)
    } catch { /* not in Electron */ }
  }

  const toggleDir = (path: string) => {
    const next = new Set(expandedDirs)
    if (next.has(path)) next.delete(path)
    else next.add(path)
    setExpandedDirs(next)
  }

  // Filter tree by search
  const filterTree = (nodes: FileTreeNode[], query: string): FileTreeNode[] => {
    if (!query.trim()) return nodes
    const q = query.toLowerCase()
    return nodes.reduce<FileTreeNode[]>((acc, node) => {
      if (node.name.toLowerCase().includes(q)) {
        acc.push(node)
      } else if (node.type === 'directory' && node.children) {
        const filtered = filterTree(node.children, query)
        if (filtered.length > 0) {
          acc.push({ ...node, children: filtered })
        }
      }
      return acc
    }, [])
  }

  const displayTree = filterTree(fileTree, searchQuery)

  return (
    <div
      className="w-[280px] h-full border-l border-border flex flex-col animate-slide-in-right"
      style={{ background: 'var(--surface-primary)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <FolderOpen size={14} className="text-primary-500 shrink-0" />
          <span className="text-xs font-semibold text-text-primary truncate">
            {currentProject.name}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleRefresh}
            className="p-1 text-text-tertiary hover:text-text-primary rounded transition-colors"
            title="刷新"
          >
            <RefreshCw size={13} />
          </button>
          <button
            onClick={toggleProjectFiles}
            className="p-1 text-text-tertiary hover:text-text-primary rounded transition-colors"
            title="关闭"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab('files')}
          className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${
            activeTab === 'files'
              ? 'text-text-primary border-b-2 border-primary-500'
              : 'text-text-tertiary hover:text-text-secondary'
          }`}
        >
          文件
        </button>
        <button
          onClick={() => setActiveTab('changes')}
          className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${
            activeTab === 'changes'
              ? 'text-text-primary border-b-2 border-primary-500'
              : 'text-text-tertiary hover:text-text-secondary'
          }`}
        >
          变更
        </button>
      </div>

      {activeTab === 'files' ? (
        <>
          {/* Search */}
          <div className="px-3 py-2 border-b border-border">
            <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg" style={{ background: 'var(--surface-tertiary)' }}>
              <Search size={12} className="text-text-tertiary shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索文件..."
                className="flex-1 bg-transparent outline-none text-xs text-text-primary placeholder-text-tertiary"
              />
            </div>
          </div>

          {/* File tree */}
          <div className="flex-1 overflow-y-auto py-1">
            {displayTree.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-text-tertiary px-4">
                <FolderOpen size={32} className="mb-2 opacity-30" />
                <p className="text-xs text-center">
                  {fileTree.length === 0 ? '加载项目文件中...\n请确保 Electron 环境可用' : '无匹配文件'}
                </p>
              </div>
            ) : (
              <TreeView nodes={displayTree} expandedDirs={expandedDirs} toggleDir={toggleDir} depth={0} />
            )}
          </div>
        </>
      ) : (
        /* Changes tab placeholder */
        <div className="flex-1 flex flex-col items-center justify-center text-text-tertiary px-4">
          <GitBranch size={32} className="mb-2 opacity-30" />
          <p className="text-xs text-center">Git 变更追踪</p>
          <p className="text-[10px] mt-1 opacity-60">连接 Agent 后自动显示代码变更</p>
        </div>
      )}

      {/* Footer: path */}
      <div className="px-3 py-2 border-t border-border">
        <p className="text-[10px] text-text-tertiary truncate" title={currentProject.path}>
          {currentProject.path}
        </p>
      </div>
    </div>
  )
}

// Recursive tree view
function TreeView({
  nodes, expandedDirs, toggleDir, depth
}: {
  nodes: FileTreeNode[]
  expandedDirs: Set<string>
  toggleDir: (path: string) => void
  depth: number
}) {
  // Sort: directories first, then files, alphabetically
  const sorted = [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'directory' ? -1 : 1
    return a.name.localeCompare(b.name)
  })

  return (
    <>
      {sorted.map((node) => (
        <TreeNode
          key={node.path}
          node={node}
          expandedDirs={expandedDirs}
          toggleDir={toggleDir}
          depth={depth}
        />
      ))}
    </>
  )
}

function TreeNode({
  node, expandedDirs, toggleDir, depth
}: {
  node: FileTreeNode
  expandedDirs: Set<string>
  toggleDir: (path: string) => void
  depth: number
}) {
  const isDir = node.type === 'directory'
  const isExpanded = expandedDirs.has(node.path)
  const paddingLeft = 8 + depth * 16

  const handleClick = () => {
    if (isDir) {
      toggleDir(node.path)
    } else {
      // Could open file in editor or send to Agent
      // For now, just a visual selection
    }
  }

  return (
    <>
      <button
        onClick={handleClick}
        className="w-full flex items-center gap-1.5 py-1 pr-2 text-left hover:bg-surface-tertiary transition-colors group"
        style={{ paddingLeft: `${paddingLeft}px` }}
      >
        {/* Expand icon for dirs */}
        {isDir ? (
          <span className="text-text-tertiary shrink-0">
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        ) : (
          <span className="w-3 shrink-0" /> /* spacer for alignment */
        )}

        {/* Icon */}
        <span className="shrink-0">
          {isDir ? (
            <FolderOpen size={14} className={isExpanded ? 'text-primary-400' : 'text-text-tertiary'} />
          ) : (
            getFileIcon(node.name)
          )}
        </span>

        {/* Name */}
        <span className={`text-xs truncate ${isDir ? 'font-medium text-text-primary' : 'text-text-secondary'}`}>
          {node.name}
        </span>
      </button>

      {/* Children */}
      {isDir && isExpanded && node.children && (
        <TreeView
          nodes={node.children}
          expandedDirs={expandedDirs}
          toggleDir={toggleDir}
          depth={depth + 1}
        />
      )}
    </>
  )
}
