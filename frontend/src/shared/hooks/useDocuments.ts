import { useAppStore } from './useStore'
import * as api from '../api/client'

export function useDocuments() {
  const store = useAppStore()

  const load = async (params?: Parameters<typeof api.getDocuments>[0]) => {
    store.setLoading(true)
    store.setError(null)
    try {
      const merged = { limit: 200, ...params }
      const data = await api.getDocuments(merged)
      console.log('[useDocuments] loaded', data.documents?.length, 'docs')
      store.setDocuments(data.documents)
      return data
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load documents'
      store.setError(msg)
      console.error('[useDocuments] load failed:', msg)
      throw err
    } finally {
      store.setLoading(false)
    }
  }

  const search = async (query: string) => {
    if (!query.trim()) {
      store.setSearchResults([])
      return
    }
    store.setLoading(true)
    try {
      const results = await api.search(query, {
        scope: store.activeScope || undefined,
        doc_type: store.activeDocType || undefined,
      })
      store.setSearchResults(results)
      return results
    } catch (err) {
      store.setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      store.setLoading(false)
    }
  }

  return { load, search, ...store }
}

export function useStats() {
  const store = useAppStore()

  const load = async () => {
    try {
      const stats = await api.getStats()
      store.setStats(stats)
      return stats
    } catch (err) {
      console.error('[useStats] load failed:', err instanceof Error ? err.message : err)
    }
  }

  const loadScopes = async () => {
    try {
      const scopes = await api.getScopes()
      store.setScopes(scopes)
      return scopes
    } catch (err) {
      console.error('[useStats] loadScopes failed:', err instanceof Error ? err.message : err)
    }
  }

  return { load, loadScopes, stats: store.stats, scopes: store.scopes }
}
