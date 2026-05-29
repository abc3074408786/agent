/**
 * Codex ACP Bridge Service
 * 
 * 通过 Electron IPC 与 Codex CLI 进程通信（ACP 协议 - JSON-RPC 2.0 over stdio）
 * 支持：启动/停止 Codex、创建会话、发送消息、接收流式响应
 */

import { useAppStore } from '../store'

type CodexMessageHandler = (content: string) => void
type CodexToolCallHandler = (toolCall: { name: string; args: any }) => void
type CodexDoneHandler = () => void
type CodexErrorHandler = (error: string) => void

interface CodexListeners {
  onContent?: CodexMessageHandler
  onToolCall?: CodexToolCallHandler
  onDone?: CodexDoneHandler
  onError?: CodexErrorHandler
}

let currentSessionId: string | null = null
let listeners: CodexListeners = {}
let initialized = false

/**
 * 初始化 Codex 消息监听
 */
export function initCodexListeners(): void {
  if (initialized || !window.electronAPI?.codex) return
  initialized = true

  window.electronAPI.codex.onMessage((msg: any) => {
    // Handle JSON-RPC responses and notifications
    if (msg.result) {
      // Response to a request
      if (msg.result.sessionId) {
        currentSessionId = msg.result.sessionId
      }
      // Initialization response
      if (msg.result.capabilities) {
        console.log('[Codex] Initialized:', msg.result)
      }
    }

    // Handle streaming content notifications
    if (msg.method === 'session/event') {
      const event = msg.params
      if (event?.type === 'text' || event?.type === 'content') {
        listeners.onContent?.(event.text || event.content || '')
      } else if (event?.type === 'tool_call' || event?.type === 'toolCall') {
        listeners.onToolCall?.({
          name: event.name || event.toolName || 'unknown',
          args: event.args || event.arguments || {}
        })
      } else if (event?.type === 'done' || event?.type === 'complete') {
        listeners.onDone?.()
      } else if (event?.type === 'error') {
        listeners.onError?.(event.message || event.error || 'Unknown error')
      }
    }

    // Alternative: some agents send parts directly in result
    if (msg.result?.parts) {
      for (const part of msg.result.parts) {
        if (part.type === 'text') {
          listeners.onContent?.(part.text)
        }
      }
      listeners.onDone?.()
    }
  })

  window.electronAPI.codex.onError((error: string) => {
    console.error('[Codex] Error:', error)
    listeners.onError?.(error)
  })

  window.electronAPI.codex.onDisconnected(({ code }) => {
    console.log('[Codex] Disconnected with code:', code)
    currentSessionId = null
    useAppStore.getState().addToast({
      type: 'warning',
      title: 'Codex 已断开',
      description: `进程退出 (code: ${code})`
    })
  })

  window.electronAPI.codex.onLog((log: string) => {
    console.log('[Codex Log]', log)
  })
}

/**
 * 启动 Codex CLI 并创建会话
 */
export async function startCodex(cwd: string): Promise<{ success: boolean; error?: string }> {
  if (!window.electronAPI?.codex) {
    return { success: false, error: 'Electron API not available' }
  }

  // Start the process
  const startResult = await window.electronAPI.codex.start(cwd)
  if (!startResult.success) {
    return startResult
  }

  // Wait a moment for initialization
  await new Promise(resolve => setTimeout(resolve, 500))

  // Create session
  const sessionResult = await window.electronAPI.codex.createSession(cwd)
  if (!sessionResult.success) {
    return sessionResult
  }

  return { success: true }
}

/**
 * 停止 Codex
 */
export async function stopCodex(): Promise<void> {
  if (window.electronAPI?.codex) {
    await window.electronAPI.codex.stop()
  }
  currentSessionId = null
}

/**
 * 通过 Codex 发送消息（流式）
 */
export async function sendCodexMessage(
  content: string,
  onChunk: (chunk: string) => void,
  signal?: AbortSignal
): Promise<string> {
  if (!window.electronAPI?.codex) {
    throw new Error('Electron API not available')
  }

  if (!currentSessionId) {
    throw new Error('No active Codex session. Please start Codex first.')
  }

  return new Promise<string>((resolve, reject) => {
    let fullContent = ''

    // Set up listeners for this message
    listeners = {
      onContent: (chunk: string) => {
        fullContent += chunk
        onChunk(chunk)
      },
      onToolCall: (toolCall) => {
        const toolMsg = `\n🔧 **${toolCall.name}**\n\`\`\`json\n${JSON.stringify(toolCall.args, null, 2)}\n\`\`\`\n`
        fullContent += toolMsg
        onChunk(toolMsg)
      },
      onDone: () => {
        listeners = {}
        resolve(fullContent)
      },
      onError: (error: string) => {
        listeners = {}
        reject(new Error(error))
      }
    }

    // Handle abort
    if (signal) {
      signal.addEventListener('abort', () => {
        listeners = {}
        reject(new DOMException('Aborted', 'AbortError'))
      })
    }

    // Send the message
    window.electronAPI.codex.sendMessage(currentSessionId!, content).then((result) => {
      if (!result.success) {
        listeners = {}
        reject(new Error(result.error || 'Failed to send message'))
      }
    })

    // Timeout fallback (60 seconds)
    setTimeout(() => {
      if (listeners.onDone) {
        listeners = {}
        resolve(fullContent || '(Codex 响应超时)')
      }
    }, 60000)
  })
}

/**
 * 获取 Codex 运行状态
 */
export async function getCodexStatus(): Promise<boolean> {
  if (!window.electronAPI?.codex) return false
  const { running } = await window.electronAPI.codex.status()
  return running
}

/**
 * 获取当前 session ID
 */
export function getCodexSessionId(): string | null {
  return currentSessionId
}
