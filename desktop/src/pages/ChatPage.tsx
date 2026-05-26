import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useAppStore, Message } from '../store'
import InputBox from '../components/InputBox'
import MessageBubble from '../components/MessageBubble'
import { Bot } from 'lucide-react'

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const { sessions, setCurrentSession, addMessage, updateLastMessage } = useAppStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)

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

  const handleSend = async (content: string) => {
    if (!sessionId) return

    // 添加用户消息
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now()
    }
    addMessage(sessionId, userMessage)

    // 添加助手占位消息
    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: Date.now()
    }
    addMessage(sessionId, assistantMessage)

    // 调用 API（后续在 API 服务层实现）
    try {
      const { agentService } = await import('../services/agent')
      await agentService.chat(
        content,
        session?.messages || [],
        session?.agentType,
        (chunk: string) => {
          // 流式更新
          const currentSession = useAppStore.getState().sessions.find((s) => s.id === sessionId)
          const lastMsg = currentSession?.messages[currentSession.messages.length - 1]
          if (lastMsg) {
            updateLastMessage(sessionId, lastMsg.content + chunk)
          }
        }
      )
    } catch (error) {
      updateLastMessage(sessionId, `抱歉，请求出错：${error instanceof Error ? error.message : '未知错误'}`)
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
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 底部输入框 */}
      <div className="px-4 pb-4 pt-2">
        <div className="max-w-3xl mx-auto">
          <InputBox onSend={handleSend} placeholder="输入消息..." />
        </div>
      </div>
    </div>
  )
}
