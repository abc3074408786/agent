import { useEffect, useRef, useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAppStore, Message } from '../store'
import MessageBubble from '../components/MessageBubble'
import { ModelSelector, PermissionSelector } from '../components/ModelSelector'
import { Bot, Send, Plus, Square, FileCode } from 'lucide-react'

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const {
    sessions, setCurrentSession, addMessage, appendToLastMessage, updateLastMessage,
    isGenerating, setIsGenerating, setAbortController, abortController,
    pendingSessionId, setPendingSessionId, settings, toggleArtifactsPanel
  } = useAppStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hasSentPendingRef = useRef(false)
  const [inputText, setInputText] = useState('')

  const session = sessions.find((s) => s.id === sessionId)

  useEffect(() => {
    if (sessionId) setCurrentSession(sessionId)
  }, [sessionId, setCurrentSession])

  // Auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages])

  // Auto-trigger from WelcomePage
  useEffect(() => {
    if (
      sessionId && pendingSessionId === sessionId && session &&
      session.messages.length === 1 && session.messages[0].role === 'user' &&
      !hasSentPendingRef.current && !isGenerating
    ) {
      hasSentPendingRef.current = true
      setPendingSessionId(null)
      triggerAIResponse(session.messages[0].content)
    }
  }, [sessionId, pendingSessionId, session, isGenerating])

  useEffect(() => {
    hasSentPendingRef.current = false
  }, [sessionId])

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

  const handleSend = async () => {
    const content = inputText.trim()
    if (!content || !sessionId || isGenerating) return

    setInputText('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now()
    }
    addMessage(sessionId, userMessage)
    await triggerAIResponse(content)
  }

  const handleStop = () => {
    if (abortController) abortController.abort()
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
      <div className="flex items-center justify-center h-full text-text-tertiary">
        会话不存在
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--surface-primary)' }}>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {session.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
            <Bot size={48} className="mb-3 opacity-30" />
            <p className="text-sm">开始你的对话吧</p>
            {session.agentType && (
              <p className="text-xs mt-1 opacity-60">
                当前助手：{session.agentType}
              </p>
            )}
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {session.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Loading indicator */}
            {isGenerating && session.messages[session.messages.length - 1]?.content === '' && (
              <div className="flex items-center gap-2 text-text-tertiary text-sm pl-11">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span>正在思考...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Stop button */}
      {isGenerating && (
        <div className="flex justify-center pb-2">
          <button
            onClick={handleStop}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-full border border-border transition-colors text-text-secondary hover:text-text-primary"
            style={{ background: 'var(--surface-secondary)' }}
          >
            <Square size={12} fill="currentColor" />
            停止生成
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="px-6 pb-4 pt-2">
        <div className="max-w-3xl mx-auto">
          <div
            className="relative rounded-xl border border-border shadow-sm"
            style={{ background: 'var(--input-bg)' }}
          >
            {/* Text input */}
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
                className="w-full resize-none outline-none text-sm bg-transparent leading-6 max-h-[200px] text-text-primary placeholder-text-tertiary"
              />
            </div>

            {/* Toolbar */}
            <div className="flex items-center justify-between px-3 pb-2.5">
              {/* Left: Attach + Artifacts */}
              <div className="flex items-center gap-1">
                <button className="p-1.5 text-text-tertiary hover:text-text-primary rounded-lg hover:bg-surface-tertiary transition-colors">
                  <Plus size={16} />
                </button>
                <button
                  onClick={toggleArtifactsPanel}
                  className={`p-1.5 rounded-lg transition-colors ${
                    settings.artifactsPanelOpen
                      ? 'text-primary-500 bg-primary-500/10'
                      : 'text-text-tertiary hover:text-text-primary hover:bg-surface-tertiary'
                  }`}
                  title="Artifacts 面板"
                >
                  <FileCode size={16} />
                </button>
              </div>

              {/* Right: Model + Agent + Send */}
              <div className="flex items-center gap-2">
                <ModelSelector />
                <PermissionSelector />

                <button
                  onClick={handleSend}
                  disabled={!inputText.trim() || isGenerating}
                  className={`p-2 rounded-lg transition-colors ${
                    inputText.trim() && !isGenerating
                      ? 'bg-primary-500 text-white hover:bg-primary-600'
                      : 'text-text-tertiary'
                  }`}
                  style={!inputText.trim() || isGenerating ? { background: 'var(--surface-tertiary)' } : undefined}
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
