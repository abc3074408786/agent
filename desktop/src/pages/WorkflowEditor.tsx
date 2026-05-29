import { useState, useCallback, useRef, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ReactFlow, Background, Controls, MiniMap, Panel,
  useNodesState, useEdgesState, addEdge, Connection,
  Node, Edge, MarkerType, Handle, Position, NodeProps
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  Plus, Play, Save, Trash2, ArrowLeft, Clock, Bot,
  GitBranch, RotateCcw, Timer, Variable, Circle, Square,
  Zap, Download, Upload
} from 'lucide-react'
import { useAppStore, WorkflowNodeData, Workflow, ExpertCategory, EXPERT_CATEGORIES } from '../store'

// ============ Custom Node Components ============


function ExpertNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  const expert = useAppStore.getState().experts.find(e => e.id === data.expertId)
  const statusColor = {
    idle: 'border-border', running: 'border-accent-blue ring-2 ring-blue-200',
    completed: 'border-accent-green', failed: 'border-accent-red', skipped: 'border-text-tertiary'
  }[data.status || 'idle']

  return (
    <div className={`px-4 py-3 rounded-xl border-2 min-w-[180px] transition-all ${statusColor} ${selected ? 'shadow-lg' : 'shadow-sm'}`}
      style={{ background: 'var(--surface-secondary)' }}>
      <Handle type="target" position={Position.Top} className="!bg-primary-500 !w-3 !h-3 !border-2 !border-white" />
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-lg">{expert?.icon || '🤖'}</span>
        <span className="text-xs font-semibold text-text-primary truncate">{data.label}</span>
      </div>
      {data.prompt && <p className="text-[10px] text-text-tertiary line-clamp-2">{data.prompt}</p>}
      {data.status === 'running' && <div className="mt-1.5 h-1 bg-surface-tertiary rounded-full overflow-hidden"><div className="h-full bg-accent-blue rounded-full animate-pulse w-3/5" /></div>}
      {data.durationMs && <p className="text-[9px] text-text-tertiary mt-1">{(data.durationMs/1000).toFixed(1)}s</p>}
      <Handle type="source" position={Position.Bottom} className="!bg-primary-500 !w-3 !h-3 !border-2 !border-white" />
    </div>
  )
}


function ConditionNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  return (
    <div className={`px-4 py-3 rounded-xl border-2 min-w-[160px] ${selected ? 'border-accent-amber shadow-lg' : 'border-amber-300 shadow-sm'}`}
      style={{ background: 'var(--surface-secondary)' }}>
      <Handle type="target" position={Position.Top} className="!bg-accent-amber !w-3 !h-3 !border-2 !border-white" />
      <div className="flex items-center gap-2 mb-1">
        <GitBranch size={14} className="text-accent-amber" />
        <span className="text-xs font-semibold text-text-primary">{data.label}</span>
      </div>
      {data.condition && <p className="text-[10px] text-text-tertiary font-mono">{data.condition}</p>}
      <Handle type="source" position={Position.Bottom} id="true" className="!bg-accent-green !w-3 !h-3 !border-2 !border-white !left-[30%]" />
      <Handle type="source" position={Position.Bottom} id="false" className="!bg-accent-red !w-3 !h-3 !border-2 !border-white !left-[70%]" />
    </div>
  )
}

function LoopNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  return (
    <div className={`px-4 py-3 rounded-xl border-2 min-w-[160px] ${selected ? 'border-purple-500 shadow-lg' : 'border-purple-300 shadow-sm'}`}
      style={{ background: 'var(--surface-secondary)' }}>
      <Handle type="target" position={Position.Top} className="!bg-purple-500 !w-3 !h-3 !border-2 !border-white" />
      <div className="flex items-center gap-2 mb-1">
        <RotateCcw size={14} className="text-purple-500" />
        <span className="text-xs font-semibold text-text-primary">{data.label}</span>
      </div>
      <p className="text-[10px] text-text-tertiary">
        {data.loopCron ? `定时: ${data.loopCron}` : `重复 ${data.loopCount || '∞'} 次`}
      </p>
      <Handle type="source" position={Position.Bottom} className="!bg-purple-500 !w-3 !h-3 !border-2 !border-white" />
    </div>
  )
}


function DelayNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  return (
    <div className={`px-4 py-3 rounded-xl border-2 min-w-[140px] ${selected ? 'border-cyan-500 shadow-lg' : 'border-cyan-300 shadow-sm'}`}
      style={{ background: 'var(--surface-secondary)' }}>
      <Handle type="target" position={Position.Top} className="!bg-cyan-500 !w-3 !h-3 !border-2 !border-white" />
      <div className="flex items-center gap-2">
        <Timer size={14} className="text-cyan-500" />
        <span className="text-xs font-semibold text-text-primary">{data.label}</span>
      </div>
      <p className="text-[10px] text-text-tertiary mt-0.5">{formatDelay(data.delayMs || 0)}</p>
      <Handle type="source" position={Position.Bottom} className="!bg-cyan-500 !w-3 !h-3 !border-2 !border-white" />
    </div>
  )
}

function VariableNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  return (
    <div className={`px-4 py-3 rounded-xl border-2 min-w-[140px] ${selected ? 'border-orange-500 shadow-lg' : 'border-orange-300 shadow-sm'}`}
      style={{ background: 'var(--surface-secondary)' }}>
      <Handle type="target" position={Position.Top} className="!bg-orange-500 !w-3 !h-3 !border-2 !border-white" />
      <div className="flex items-center gap-2">
        <Variable size={14} className="text-orange-500" />
        <span className="text-xs font-semibold text-text-primary">{data.label}</span>
      </div>
      {data.variableName && <p className="text-[10px] text-text-tertiary font-mono mt-0.5">${`{${data.variableName}}`}</p>}
      <Handle type="source" position={Position.Bottom} className="!bg-orange-500 !w-3 !h-3 !border-2 !border-white" />
    </div>
  )
}

function StartNode({ data }: NodeProps<WorkflowNodeData>) {
  return (
    <div className="px-4 py-2 rounded-full border-2 border-accent-green shadow-sm" style={{ background: 'var(--surface-secondary)' }}>
      <div className="flex items-center gap-2">
        <Circle size={12} className="text-accent-green fill-accent-green" />
        <span className="text-xs font-semibold text-text-primary">开始</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-accent-green !w-3 !h-3 !border-2 !border-white" />
    </div>
  )
}

function EndNode({ data }: NodeProps<WorkflowNodeData>) {
  return (
    <div className="px-4 py-2 rounded-full border-2 border-accent-red shadow-sm" style={{ background: 'var(--surface-secondary)' }}>
      <Handle type="target" position={Position.Top} className="!bg-accent-red !w-3 !h-3 !border-2 !border-white" />
      <div className="flex items-center gap-2">
        <Square size={12} className="text-accent-red fill-accent-red" />
        <span className="text-xs font-semibold text-text-primary">结束</span>
      </div>
    </div>
  )
}

function formatDelay(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms/1000).toFixed(0)}s`
  if (ms < 3600000) return `${(ms/60000).toFixed(0)}min`
  return `${(ms/3600000).toFixed(1)}h`
}


// ============ Node Types Registry ============
const nodeTypes = {
  expert: ExpertNode,
  condition: ConditionNode,
  loop: LoopNode,
  delay: DelayNode,
  variable: VariableNode,
  start: StartNode,
  end: EndNode,
}

// ============ Node Panel (drag source) ============
const NODE_TEMPLATES = [
  { type: 'expert', label: '专家节点', icon: '🤖', color: 'text-primary-500' },
  { type: 'condition', label: '条件判断', icon: '⑂', color: 'text-accent-amber' },
  { type: 'loop', label: '循环', icon: '🔄', color: 'text-purple-500' },
  { type: 'delay', label: '延时', icon: '⏱️', color: 'text-cyan-500' },
  { type: 'variable', label: '变量', icon: '𝑥', color: 'text-orange-500' },
]

// ============ Main Component ============
export default function WorkflowEditor() {
  const navigate = useNavigate()
  const { id: workflowId } = useParams<{ id: string }>()
  const { workflows, saveWorkflow, updateWorkflow, experts, hiredExpertIds, addToast } = useAppStore()

  // Load existing workflow or start fresh
  const existingWorkflow = workflowId ? workflows.find(w => w.id === workflowId) : null

  const defaultNodes: Node[] = existingWorkflow?.nodes || [
    { id: 'start-1', type: 'start', position: { x: 250, y: 50 }, data: { label: '开始', type: 'start' } },
    { id: 'end-1', type: 'end', position: { x: 250, y: 400 }, data: { label: '结束', type: 'end' } },
  ]
  const defaultEdges: Edge[] = existingWorkflow?.edges || []

  const [nodes, setNodes, onNodesChange] = useNodesState(defaultNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(defaultEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [workflowName, setWorkflowName] = useState(existingWorkflow?.name || '新工作流')
  const [workflowDesc, setWorkflowDesc] = useState(existingWorkflow?.description || '')
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  const hiredExperts = useMemo(() =>
    experts.filter(e => hiredExpertIds.includes(e.id)),
    [experts, hiredExpertIds]
  )

  // Connect edges
  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge({
      ...params,
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      style: { strokeWidth: 2 },
      animated: true,
    }, eds))
  }, [setEdges])


  // Drag and drop from panel
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    const type = event.dataTransfer.getData('application/reactflow-type')
    if (!type || !reactFlowWrapper.current) return

    const bounds = reactFlowWrapper.current.getBoundingClientRect()
    const position = { x: event.clientX - bounds.left - 90, y: event.clientY - bounds.top - 25 }
    const id = `${type}-${Date.now()}`

    const dataMap: Record<string, WorkflowNodeData> = {
      expert: { label: '专家', type: 'expert', expertId: hiredExperts[0]?.id || '', prompt: '' },
      condition: { label: '条件判断', type: 'condition', condition: 'result.success === true' },
      loop: { label: '循环', type: 'loop', loopCount: 3 },
      delay: { label: '延时', type: 'delay', delayMs: 5000 },
      variable: { label: '变量', type: 'variable', variableName: 'output', variableValue: '' },
    }

    const newNode: Node = { id, type, position, data: dataMap[type] || { label: type, type: type as any } }
    setNodes((nds) => [...nds, newNode])
  }, [setNodes, hiredExperts])

  // Select node for editing
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  // Update selected node data
  const updateNodeData = (field: string, value: any) => {
    if (!selectedNode) return
    setNodes((nds) => nds.map((n) =>
      n.id === selectedNode.id ? { ...n, data: { ...n.data, [field]: value } } : n
    ))
    setSelectedNode((prev) => prev ? { ...prev, data: { ...prev.data, [field]: value } } : null)
  }

  // Delete selected node
  const deleteSelectedNode = () => {
    if (!selectedNode) return
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))
    setSelectedNode(null)
  }

  // Save workflow
  const handleSave = () => {
    const workflow = { name: workflowName, description: workflowDesc, icon: '⚡', nodes, edges, category: 'operations' as ExpertCategory }
    if (existingWorkflow) {
      updateWorkflow(existingWorkflow.id, workflow)
      addToast({ type: 'success', title: '工作流已更新' })
    } else {
      const id = saveWorkflow(workflow)
      addToast({ type: 'success', title: '工作流已保存' })
      navigate(`/workflows/${id}`, { replace: true })
    }
  }

  // Export JSON
  const handleExport = () => {
    const data = JSON.stringify({ name: workflowName, description: workflowDesc, nodes, edges }, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${workflowName}.workflow.json`; a.click()
    URL.revokeObjectURL(url)
  }

  // Run workflow (mock)
  const handleRun = async () => {
    addToast({ type: 'info', title: '工作流开始执行', description: `${nodes.filter(n => n.type === 'expert').length} 个专家节点` })
    // TODO: implement real execution via backend/Codex
  }


  return (
    <div className="flex h-full overflow-hidden" style={{ background: 'var(--surface-primary)' }}>
      {/* Left: Node panel */}
      <div className="w-56 border-r border-border flex flex-col" style={{ background: 'var(--sidebar-bg)' }}>
        {/* Header */}
        <div className="px-3 py-3 border-b border-border">
          <button onClick={() => navigate('/workflows')} className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors mb-2">
            <ArrowLeft size={12} />
            返回列表
          </button>
          <input
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            className="w-full text-sm font-bold text-text-primary bg-transparent outline-none border-b border-transparent focus:border-primary-500 pb-0.5"
          />
        </div>

        {/* Draggable nodes */}
        <div className="px-3 py-3">
          <p className="text-[10px] text-text-tertiary font-semibold uppercase tracking-wider mb-2">拖拽添加节点</p>
          <div className="space-y-1.5">
            {NODE_TEMPLATES.map((tpl) => (
              <div
                key={tpl.type}
                draggable
                onDragStart={(e) => { e.dataTransfer.setData('application/reactflow-type', tpl.type); e.dataTransfer.effectAllowed = 'move' }}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg border border-border cursor-grab active:cursor-grabbing hover:border-text-tertiary hover:shadow-sm transition-all"
                style={{ background: 'var(--surface-secondary)' }}
              >
                <span className="text-sm">{tpl.icon}</span>
                <span className="text-xs font-medium text-text-primary">{tpl.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick experts */}
        {hiredExperts.length > 0 && (
          <div className="px-3 py-3 border-t border-border">
            <p className="text-[10px] text-text-tertiary font-semibold uppercase tracking-wider mb-2">已雇专家</p>
            <div className="space-y-1">
              {hiredExperts.slice(0, 8).map((expert) => (
                <div
                  key={expert.id}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData('application/reactflow-type', 'expert')
                    e.dataTransfer.setData('expertId', expert.id)
                    e.dataTransfer.effectAllowed = 'move'
                  }}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-grab active:cursor-grabbing hover:bg-surface-tertiary transition-colors"
                >
                  <span className="text-sm">{expert.icon}</span>
                  <span className="text-[11px] text-text-secondary truncate">{expert.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>


      {/* Center: Canvas */}
      <div className="flex-1 relative" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onDragOver={onDragOver}
          onDrop={onDrop}
          onNodeClick={onNodeClick}
          onPaneClick={() => setSelectedNode(null)}
          nodeTypes={nodeTypes}
          fitView
          defaultEdgeOptions={{ markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 }, style: { strokeWidth: 2 }, animated: true }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} color="var(--border-primary)" />
          <Controls position="bottom-left" className="!bg-surface-secondary !border-border !shadow-lg !rounded-xl" />
          <MiniMap position="bottom-right" className="!bg-surface-secondary !border-border !rounded-xl" nodeColor="var(--text-tertiary)" />

          {/* Top toolbar */}
          <Panel position="top-right">
            <div className="flex items-center gap-2">
              <button onClick={handleRun} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-accent-green rounded-lg hover:bg-green-600 transition-colors shadow-sm">
                <Play size={12} /> 运行
              </button>
              <button onClick={handleSave} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-primary-500 rounded-lg hover:bg-primary-600 transition-colors shadow-sm">
                <Save size={12} /> 保存
              </button>
              <button onClick={handleExport} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-text-secondary hover:text-text-primary hover:bg-surface-tertiary transition-colors" style={{ background: 'var(--surface-primary)' }}>
                <Download size={12} /> 导出
              </button>
            </div>
          </Panel>
        </ReactFlow>
      </div>


      {/* Right: Node Properties */}
      {selectedNode && selectedNode.type !== 'start' && selectedNode.type !== 'end' && (
        <div className="w-72 border-l border-border overflow-y-auto" style={{ background: 'var(--surface-secondary)' }}>
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">节点属性</h3>
            <button onClick={deleteSelectedNode} className="p-1.5 text-text-tertiary hover:text-accent-red rounded-lg hover:bg-surface-tertiary transition-colors" title="删除节点">
              <Trash2 size={14} />
            </button>
          </div>
          <div className="px-4 py-4 space-y-4">
            {/* Label */}
            <div>
              <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">名称</label>
              <input value={selectedNode.data.label || ''} onChange={(e) => updateNodeData('label', e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary outline-none focus:ring-2 focus:ring-primary-500"
                style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
            </div>

            {/* Expert-specific */}
            {selectedNode.type === 'expert' && (
              <>
                <div>
                  <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">选择专家</label>
                  <select value={selectedNode.data.expertId || ''} onChange={(e) => updateNodeData('expertId', e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary outline-none"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }}>
                    <option value="">选择...</option>
                    {experts.map((e) => <option key={e.id} value={e.id}>{e.icon} {e.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">指令 Prompt</label>
                  <textarea value={selectedNode.data.prompt || ''} onChange={(e) => updateNodeData('prompt', e.target.value)}
                    rows={4} placeholder="给专家的指令..."
                    className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary placeholder-text-tertiary resize-none outline-none focus:ring-2 focus:ring-primary-500"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
                  <p className="text-[9px] text-text-tertiary mt-1">支持变量: {'${output}'}, {'${prev_result}'}</p>
                </div>
              </>
            )}

            {/* Condition-specific */}
            {selectedNode.type === 'condition' && (
              <div>
                <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">条件表达式</label>
                <input value={selectedNode.data.condition || ''} onChange={(e) => updateNodeData('condition', e.target.value)}
                  placeholder="result.success === true"
                  className="w-full px-3 py-1.5 rounded-lg text-xs font-mono text-text-primary placeholder-text-tertiary outline-none focus:ring-2 focus:ring-primary-500"
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
                <p className="text-[9px] text-text-tertiary mt-1">绿色出口=true, 红色出口=false</p>
              </div>
            )}

            {/* Loop-specific */}
            {selectedNode.type === 'loop' && (
              <>
                <div>
                  <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">重复次数 (0=无限)</label>
                  <input type="number" value={selectedNode.data.loopCount || 0} onChange={(e) => updateNodeData('loopCount', parseInt(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary outline-none"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
                </div>
                <div>
                  <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">定时 Cron（可选）</label>
                  <input value={selectedNode.data.loopCron || ''} onChange={(e) => updateNodeData('loopCron', e.target.value)}
                    placeholder="0 */1 * * * (每小时)"
                    className="w-full px-3 py-1.5 rounded-lg text-xs font-mono text-text-primary placeholder-text-tertiary outline-none"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
                </div>
              </>
            )}

            {/* Delay-specific */}
            {selectedNode.type === 'delay' && (
              <div>
                <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">延时 (毫秒)</label>
                <input type="number" value={selectedNode.data.delayMs || 0} onChange={(e) => updateNodeData('delayMs', parseInt(e.target.value))}
                  className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary outline-none"
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
                <p className="text-[9px] text-text-tertiary mt-1">= {formatDelay(selectedNode.data.delayMs || 0)}</p>
              </div>
            )}

            {/* Variable-specific */}
            {selectedNode.type === 'variable' && (
              <>
                <div>
                  <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">变量名</label>
                  <input value={selectedNode.data.variableName || ''} onChange={(e) => updateNodeData('variableName', e.target.value)}
                    placeholder="output"
                    className="w-full px-3 py-1.5 rounded-lg text-xs font-mono text-text-primary placeholder-text-tertiary outline-none"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
                </div>
                <div>
                  <label className="text-[10px] font-semibold text-text-tertiary uppercase mb-1 block">初始值</label>
                  <input value={selectedNode.data.variableValue || ''} onChange={(e) => updateNodeData('variableValue', e.target.value)}
                    placeholder="可引用上一步结果"
                    className="w-full px-3 py-1.5 rounded-lg text-xs text-text-primary placeholder-text-tertiary outline-none"
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--input-border)' }} />
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
