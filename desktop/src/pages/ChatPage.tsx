import { useEffect, useRef, useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAppStore, Message } from '../store'
import MessageBubble from '../components/MessageBubble'
import { Bot, Send, Plus, ChevronDown, Square } from 'lucide-react'

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
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hasSentPendingRef = useRef(false)
  const [inputText, setInputText] = useState('')
  const [selectedModel, setSelectedModel] = useState('mimo-v2-pro')

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

  // 从 WelcomePage 跳转后自动触发 AI 回复
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
      triggerAIResponse(session.messages[0].content)
    }
  }, [sessionId, pendingSessionId, session, isGenerating])

  useEffect(() => {
    hasSentPendingRef.current = false
  }, [sessionId])

  // 触发 AI 回复
  const triggerAIResponse = useCallback(async (content: string) => {
    if (!sessionId) return

    const controller = new AbortController()
    setAbortController(controller)
    setIsGenerating(true)

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: Date.now()
    }
    addMessage(sessionId, assistantMessage)

    try {
      const { agentService } = await import('../services/agent')
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
  const handleSend = async () => {
    const content = inputText.trim()
    if (!content || !sessionId || isGenerating) return

    setInputText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now()
    }
    addMessage(sessionId, userMessage)
    await triggerAIResponse(content)
  }

  // 停止生成
  const handleStop = () => {
    if (abortController) {
      abortController.abort()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
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
    <div className="flex flex-col h-full bg-white">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
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
            {isGenerating && session.messages[session.messages.length - 1]?.content === '' && (
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
            className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 bg-gray-50 rounded-full hover:bg-gray-100 transition-colors border border-gray-200"
          >
            <Square size={12} fill="currentColor" />
            停止生成
          </button>
        </div>
      )}

      {/* 底部输入框 - AionUi 风格 */}
      <div className="px-6 pb-4 pt-2">
        <div className="max-w-3xl mx-auto">
          <div className="relative border border-gray-200 rounded-xl bg-white shadow-sm">
            {/* 文本输入 */}
            <div className="px-4 pt-3 pb-2">
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                onInput={handleInput}
                placeholder="发送消息..."
                disabled={isGenerating}
                rows={1}
                className="w-full resize-none outline-none text-sm text-gray-700 placeholder-gray-400 bg-transparent leading-6 max-h-[200px]"
              />
            </div>

            {/* 底部工具栏 */}
            <div className="flex items-center justify-between px-3 pb-2.5">
              {/* 左侧：附件 */}
              <button className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-50 transition-colors">
                <Plus size={16} />
              </button>

              {/* 右侧：模型 + 发送 */}
              <div className="flex items-center gap-2">
                {/* 模型选择器 */}
                <button className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-500 rounded-lg hover:bg-gray-50 border border-gray-200 transition-colors">
                  <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
                  <span>{selectedModel}</span>
                  <ChevronDown size={11} />
                </button>

                {/* Agent 选择器 */}
                <button className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-500 rounded-lg hover:bg-gray-50 border border-gray-200 transition-colors">
                  <span>⊙</span>
                  <span>默认</span>
                  <ChevronDown size={11} />
                </button>

                {/* 发送按钮 */}
                <button
                  onClick={handleSend}
                  disabled={!inputText.trim() || isGenerating}
                  className={`p-2 rounded-lg transition-colors ${
                    inputText.trim() && !isGenerating
                      ? 'bg-blue-500 text-white hover:bg-blue-600'
                      : 'bg-gray-100 text-gray-300'
                  }`}
                >
                  <Send size={14} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
