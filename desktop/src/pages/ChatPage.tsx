import { useEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useAppStore, Message } from '../store'
import InputBox from '../components/InputBox'
import MessageBubble from '../components/MessageBubble'
import { Bot, Square } from 'lucide-react'

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const {
    sessions,
    setCurrentSession,
    addMessage,
    appendToLastMessage,
    updateLastMessage,
    isGenerating,
    setIsGenerating,
    setAbortController,
    abortController,
    pendingSessionId,
    setPendingSessionId
  } = useAppStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const hasSentPendingRef = useRef(false)

  const session = sessions.find((s) => s.id === sessionId)

  useEffect(() => {
    if (sessionId) {
      setCurrentSession(sessionId)
    }
  }, [sessionId, setCurrentSession])

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages])

  // P0 修复：WelcomePage 跳转后自动触发 AI 回复
  useEffect(() => {
    if (
      sessionId &&
      pendingSessionId === sessionId &&
      session &&
      session.messages.length === 1 &&
      session.messages[0].role === 'user' &&
      !hasSentPendingRef.current &&
      !isGenerating
    ) {
      hasSentPendingRef.current = true
      setPendingSessionId(null)
      // 自动发送第一条消息给 AI
      triggerAIResponse(session.messages[0].content)
    }
  }, [sessionId, pendingSessionId, session, isGenerating])

  // 重置 pending ref
  useEffect(() => {
    hasSentPendingRef.current = false
  }, [sessionId])

  // 核心：触发 AI 回复（修复竞态条件）
  const triggerAIResponse = useCallback(async (content: string) => {
    if (!sessionId) return

    const controller = new AbortController()
    setAbortController(controller)
    setIsGenerating(true)

    // 添加助手占位消息
    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: Date.now()
    }
    addMessage(sessionId, assistantMessage)

    try {
      const { agentService } = await import('../services/agent')

      // P0 修复：使用 appendToLastMessage 避免竞态条件
      await agentService.chat(
        content,
        session?.messages || [],
        session?.agentType,
        (chunk: string) => {
          appendToLastMessage(sessionId, chunk)
        },
        controller.signal
      )
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        // 用户主动停止，追加提示
        appendToLastMessage(sessionId, '\n\n[已停止生成]')
      } else {
        updateLastMessage(
          sessionId,
          `抱歉，请求出错：${error instanceof Error ? error.message : '未知错误'}`
        )
      }
    } finally {
      setIsGenerating(false)
      setAbortController(null)
    }
  }, [sessionId, session, addMessage, appendToLastMessage, updateLastMessage, setIsGenerating, setAbortController])

  // 发送消息
  const handleSend = async (content: string) => {
    if (!sessionId || isGenerating) return

    // 添加用户消息
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now()
    }
    addMessage(sessionId, userMessage)

    // 触发 AI 回复
    await triggerAIResponse(content)
  }

  // 停止生成
  const handleStop = () => {
    if (abortController) {
      abortController.abort()
    }
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        会话不存在
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {session.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Bot size={48} className="mb-3 text-gray-300" />
            <p className="text-sm">开始你的对话吧</p>
            {session.agentType && (
              <p className="text-xs mt-1 text-gray-300">
                当前助手：{session.agentType}
              </p>
            )}
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {session.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* 加载指示器 */}
            {isGenerating && (
              <div className="flex items-center gap-2 text-gray-400 text-sm pl-11">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span>正在思考...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 停止生成按钮 */}
      {isGenerating && (
        <div className="flex justify-center pb-2">
          <button
            onClick={handleStop}
            className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors border border-gray-200"
          >
            <Square size={14} fill="currentColor" />
            停止生成
          </button>
        </div>
      )}

      {/* 底部输入框 */}
      <div className="px-4 pb-4 pt-2">
        <div className="max-w-3xl mx-auto">
          <InputBox
            onSend={handleSend}
            placeholder="输入消息..."
            disabled={isGenerating}
          />
        </div>
      </div>
    </div>
  )
}
