import { useAppStore, Message } from '../store'

/**
 * Agent API 服务层
 * 支持本地 Agent 和远程 Agent 两种模式
 * 支持 SSE 流式响应 + AbortController 中断
 */

function getBaseUrl(): string {
  const settings = useAppStore.getState().settings

  if (settings.agentMode === 'local') {
    return `http://127.0.0.1:${settings.agentLocalPort}`
  }
  return settings.agentRemoteUrl
}

function getHeaders(): Record<string, string> {
  const settings = useAppStore.getState().settings
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  }

  // 如果是代理模式，添加代理 Key
  if (settings.llmMode === 'proxy' && settings.proxyKey) {
    headers['Authorization'] = `Bearer ${settings.proxyKey}`
  }

  return headers
}

export interface ChatRequest {
  message: string
  history?: Array<{ role: string; content: string }>
  model?: string
  agent_type?: string
  stream?: boolean
  // LLM 配置（用户自有 Key 时传递）
  llm_config?: {
    provider: string
    api_key: string
    model: string
  }
}

export const agentService = {
  /**
   * 发送聊天消息（流式，支持中断）
   */
  async chat(
    message: string,
    history: Message[],
    agentType?: string,
    onChunk?: (chunk: string) => void,
    signal?: AbortSignal
  ): Promise<string> {
    const settings = useAppStore.getState().settings
    const baseUrl = getBaseUrl()

    if (!baseUrl) {
      throw new Error('请先在设置中配置 Agent 服务地址')
    }

    const body: ChatRequest = {
      message,
      history: history
        .filter((m) => m.role !== 'system')
        .map((m) => ({ role: m.role, content: m.content })),
      model: settings.defaultModel,
      stream: true
    }

    if (agentType) {
      body.agent_type = agentType
    }

    // 如果是用户自有 Key 模式，附带 LLM 配置
    if (settings.llmMode === 'user_key') {
      const isAnthropic = settings.defaultModel.startsWith('claude')
      body.llm_config = {
        provider: isAnthropic ? 'anthropic' : 'openai',
        api_key: isAnthropic ? settings.anthropicKey : settings.openaiKey,
        model: settings.defaultModel
      }
    }

    const response = await fetch(`${baseUrl}/chat/stream`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body),
      signal // 支持 AbortController 中断
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Agent 请求失败 (${response.status}): ${errorText}`)
    }

    // 处理 SSE 流式响应
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法获取响应流')
    }

    const decoder = new TextDecoder()
    let fullContent = ''

    try {
      while (true) {
        // 检查是否被中断
        if (signal?.aborted) {
          reader.cancel()
          throw new DOMException('Aborted', 'AbortError')
        }

        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const lines = text.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)

            if (data === '[DONE]') {
              return fullContent
            }

            try {
              const parsed = JSON.parse(data)
              const chunk = parsed.content || parsed.delta?.content || parsed.text || ''
              if (chunk) {
                fullContent += chunk
                onChunk?.(chunk)
              }
            } catch {
              // 如果不是 JSON，直接作为文本处理
              if (data.trim()) {
                fullContent += data
                onChunk?.(data)
              }
            }
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        throw error // 向上抛出中断错误
      }
      throw error
    }

    return fullContent
  },

  /**
   * 发送聊天消息（非流式）
   */
  async chatSync(message: string, history: Message[], agentType?: string): Promise<string> {
    const settings = useAppStore.getState().settings
    const baseUrl = getBaseUrl()

    if (!baseUrl) {
      throw new Error('请先在设置中配置 Agent 服务地址')
    }

    const body: ChatRequest = {
      message,
      history: history
        .filter((m) => m.role !== 'system')
        .map((m) => ({ role: m.role, content: m.content })),
      model: settings.defaultModel,
      stream: false
    }

    if (agentType) {
      body.agent_type = agentType
    }

    if (settings.llmMode === 'user_key') {
      const isAnthropic = settings.defaultModel.startsWith('claude')
      body.llm_config = {
        provider: isAnthropic ? 'anthropic' : 'openai',
        api_key: isAnthropic ? settings.anthropicKey : settings.openaiKey,
        model: settings.defaultModel
      }
    }

    const response = await fetch(`${baseUrl}/chat`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Agent 请求失败 (${response.status}): ${errorText}`)
    }

    const data = await response.json()
    return data.response || data.content || data.message || ''
  },

  /**
   * 检查 Agent 服务健康状态
   */
  async healthCheck(): Promise<boolean> {
    const baseUrl = getBaseUrl()
    if (!baseUrl) return false

    try {
      const response = await fetch(`${baseUrl}/health`, {
        method: 'GET',
        headers: getHeaders()
      })
      return response.ok
    } catch {
      return false
    }
  },

  /**
   * 获取可用工具列表
   */
  async getTools(): Promise<string[]> {
    const baseUrl = getBaseUrl()
    if (!baseUrl) return []

    try {
      const response = await fetch(`${baseUrl}/tools`, {
        method: 'GET',
        headers: getHeaders()
      })
      if (!response.ok) return []
      const data = await response.json()
      return data.tools || []
    } catch {
      return []
    }
  },

  /**
   * 获取可用技能列表
   */
  async getSkills(): Promise<string[]> {
    const baseUrl = getBaseUrl()
    if (!baseUrl) return []

    try {
      const response = await fetch(`${baseUrl}/skills`, {
        method: 'GET',
        headers: getHeaders()
      })
      if (!response.ok) return []
      const data = await response.json()
      return data.skills || []
    } catch {
      return []
    }
  }
}
