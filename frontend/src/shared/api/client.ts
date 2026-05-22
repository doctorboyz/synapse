import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export interface Document {
  id: string
  title: string
  content: string
  scope: string
  doc_type: string
  oracle_name: string | null
  source_file: string | null
  source_project: string | null
  created_at: string
  updated_at: string
  concepts: string[] | null
  tags: string[] | null
  search_vector: string | null
}

export interface TraceNode {
  id: string
  title: string
  doc_type: string
  relation: string
  confidence: number
  depth: number
}

export interface SearchResult {
  id: string
  title: string
  content: string
  score: number
  scope: string
  doc_type: string
}

export interface Stats {
  total_documents: number
  by_type: Record<string, number>
  by_scope: Record<string, number>
  by_oracle: Record<string, number>
}

export interface Scope {
  name: string
  doc_count: number
  description: string | null
  oracle_name: string | null
}

export interface OllamaModel {
  name: string
  size: number
  modified_at: string
}

export async function getDocuments(params?: {
  scope?: string
  doc_type?: string
  limit?: number
  offset?: number
  order?: string
}): Promise<{ documents: Document[]; total: number }> {
  const res = await api.get('/documents', { params })
  // Backend may return array directly or { documents, total }
  const data = res.data
  if (Array.isArray(data)) {
    return { documents: data, total: data.length }
  }
  return data
}

export async function getDocument(id: string, includeChain = true): Promise<Document & { trace_chain?: TraceNode[] }> {
  const res = await api.get(`/documents/${id}`, { params: { include_chain: includeChain } })
  return res.data
}

export async function getTraceChain(id: string, direction = 'both', maxDepth = 5): Promise<TraceNode[]> {
  const res = await api.get(`/trace/${id}`, { params: { direction, max_depth: maxDepth } })
  return res.data
}

export async function search(query: string, options?: {
  scope?: string
  doc_type?: string
  limit?: number
  mode?: string
}): Promise<SearchResult[]> {
  const res = await api.post('/search', { query, limit: 10, mode: 'hybrid', ...options })
  return res.data
}

export async function getStats(): Promise<Stats> {
  const res = await api.get('/stats')
  return res.data
}

export async function getScopes(): Promise<Scope[]> {
  const res = await api.get('/scopes')
  return res.data
}

export async function pushDocument(data: {
  title: string
  content: string
  scope?: string
  doc_type?: string
  source_type?: string
}): Promise<{ id: string }> {
  const res = await api.post('/push', {
    title: data.title,
    content: data.content,
    scope: data.scope || 'shared',
    doc_type: data.doc_type || 'note',
    source_type: data.source_type || 'frontend',
  })
  return res.data
}

export async function uploadFile(file: File, scope = 'shared'): Promise<{ id: string; status: string }> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('scope', scope)
  const res = await api.post('/ingest/file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function ingestWebsite(url: string, scope = 'shared'): Promise<{ id: string; status: string }> {
  const res = await api.post('/ingest/website', { url, scope })
  return res.data
}

export async function ingestYoutube(url: string, scope = 'shared'): Promise<{ id: string; status: string }> {
  const res = await api.post('/ingest/youtube', { url, scope })
  return res.data
}

export async function getOllamaModels(): Promise<OllamaModel[]> {
  const res = await api.get('/models')
  return res.data
}

export async function getProjects(): Promise<{ scope: string; path: string }[]> {
  const res = await api.get('/projects')
  return res.data
}

export async function chatStream(
  query: string,
  onChunk: (chunk: string) => void,
  options?: { model?: string; scope?: string; scopes?: string[] },
  onSources?: (sources: SearchResult[]) => void,
): Promise<void> {
  const body: Record<string, unknown> = { query }
  if (options?.model) body.model = options.model
  if (options?.scopes && options.scopes.length > 0) {
    body.scopes = options.scopes
  } else if (options?.scope) {
    body.scope = options.scope
  }

  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) throw new Error(`Chat error: ${res.status}`)

  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let sourcesParsed = false

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    if (!sourcesParsed) {
      const start = buffer.indexOf('__SOURCES__')
      if (start !== -1) {
        const end = buffer.indexOf('__SOURCES__', start + 11)
        if (end !== -1) {
          const jsonStr = buffer.slice(start + 11, end)
          try {
            const sources = JSON.parse(jsonStr)
            onSources?.(sources)
          } catch {
            // ignore parse errors
          }
          buffer = buffer.slice(0, start) + buffer.slice(end + 11)
          sourcesParsed = true
        }
      }
    }

    if (sourcesParsed && buffer) {
      onChunk(buffer)
      buffer = ''
    }
  }

  // Flush remaining buffer
  if (buffer) {
    onChunk(buffer)
  }
}

export async function suggestScope(content: string, scopes?: string[]): Promise<{ scope: string; confidence: number }> {
  const res = await api.post('/suggest-scope', { content, scopes })
  return res.data
}

export async function resolveLinks(content: string, scope?: string): Promise<{ resolved: Record<string, string>; unresolved: string[] }> {
  const res = await api.post('/resolve-links', { content, scope })
  return res.data
}

export default api
