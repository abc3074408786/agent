import { useAppStore } from '../store'

/**
 * RAG 知识库 API 服务层
 * 连接远程 RAG 服务
 */

function getBaseUrl(): string {
  return useAppStore.getState().settings.ragUrl
}

function getHeaders(): Record<string, string> {
  const settings = useAppStore.getState().settings
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  }

  if (settings.ragKey) {
    headers['Authorization'] = `Bearer ${settings.ragKey}`
  }

  return headers
}

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  document_count: number
  created_at: string
}

export interface SearchResult {
  content: string
  score: number
  metadata: Record<string, string>
  source?: string
}

export const ragService = {
  /**
   * 搜索知识库
   */
  async search(
    query: string,
    knowledgeBaseId?: string,
    topK: number = 5
  ): Promise<SearchResult[]> {
    const baseUrl = getBaseUrl()
    if (!baseUrl) {
      throw new Error('请先在设置中配置 RAG 服务地址')
    }

    const response = await fetch(`${baseUrl}/search`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        query,
        knowledge_base_id: knowledgeBaseId,
        top_k: topK
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`RAG 搜索失败 (${response.status}): ${errorText}`)
    }

    const data = await response.json()
    return data.results || []
  },

  /**
   * 获取知识库列表
   */
  async listKnowledgeBases(): Promise<KnowledgeBase[]> {
    const baseUrl = getBaseUrl()
    if (!baseUrl) return []

    try {
      const response = await fetch(`${baseUrl}/knowledge_bases`, {
        method: 'GET',
        headers: getHeaders()
      })
      if (!response.ok) return []
      const data = await response.json()
      return data.knowledge_bases || data || []
    } catch {
      return []
    }
  },

  /**
   * 上传文档到知识库
   */
  async uploadDocument(
    knowledgeBaseId: string,
    file: File
  ): Promise<{ success: boolean; document_id?: string }> {
    const baseUrl = getBaseUrl()
    if (!baseUrl) {
      throw new Error('请先在设置中配置 RAG 服务地址')
    }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('knowledge_base_id', knowledgeBaseId)

    const settings = useAppStore.getState().settings
    const headers: Record<string, string> = {}
    if (settings.ragKey) {
      headers['Authorization'] = `Bearer ${settings.ragKey}`
    }

    const response = await fetch(`${baseUrl}/documents/upload`, {
      method: 'POST',
      headers,
      body: formData
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`文档上传失败 (${response.status}): ${errorText}`)
    }

    return await response.json()
  },

  /**
   * 检查 RAG 服务健康状态
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
  }
}
