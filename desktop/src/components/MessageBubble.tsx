import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check, User, Bot } from 'lucide-react'
import { useState } from 'react'
import { Message } from '../store'
import ToolCallView from './ToolCallView'

interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  if (isSystem) {
    return (
      <div className="flex justify-center my-3">
        <div className="px-4 py-2 rounded-full text-xs text-text-tertiary bg-surface-tertiary">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shrink-0 mt-1 shadow-sm">
          <Bot size={14} className="text-white" />
        </div>
      )}

      {/* Content */}
      <div className={`max-w-[80%] ${isUser ? '' : ''}`}>
        {/* Tool calls (before content) */}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <ToolCallView toolCalls={message.toolCalls} />
        )}

        {/* Message text */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-primary-500 text-white'
              : 'border border-border text-text-primary'
          }`}
          style={!isUser ? { background: 'var(--surface-secondary)' } : undefined}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
          ) : (
            <div className="markdown-body text-sm">
              {message.content ? (
                <ReactMarkdown
                  components={{
                    code({ node, className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '')
                      const isInline = !match

                      if (isInline) {
                        return (
                          <code
                            className="px-1.5 py-0.5 rounded text-xs font-mono"
                            style={{ background: 'var(--surface-tertiary)', color: 'var(--text-primary)' }}
                            {...props}
                          >
                            {children}
                          </code>
                        )
                      }

                      return (
                        <CodeBlock language={match[1]}>
                          {String(children).replace(/\n$/, '')}
                        </CodeBlock>
                      )
                    },
                    table({ children }) {
                      return <table className="w-full border-collapse my-3">{children}</table>
                    },
                    th({ children }) {
                      return (
                        <th className="border border-border px-3 py-2 text-left text-xs font-semibold" style={{ background: 'var(--surface-tertiary)' }}>
                          {children}
                        </th>
                      )
                    },
                    td({ children }) {
                      return <td className="border border-border px-3 py-2 text-xs">{children}</td>
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              ) : (
                <span className="inline-block w-2 h-4 rounded-sm animate-pulse" style={{ background: 'var(--text-tertiary)' }} />
              )}
            </div>
          )}
        </div>
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-1" style={{ background: 'var(--surface-tertiary)' }}>
          <User size={14} className="text-text-secondary" />
        </div>
      )}
    </div>
  )
}

// Code block with copy button
function CodeBlock({ language, children }: { language: string; children: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(children)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group my-3 rounded-lg overflow-hidden border border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 text-xs" style={{ background: 'var(--code-bg)', color: 'var(--text-tertiary)' }}>
        <span className="font-mono">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-text-primary transition-colors"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          <span>{copied ? '已复制' : '复制'}</span>
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: '12px 16px',
          fontSize: '12px',
          background: 'var(--code-bg)',
        }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  )
}
