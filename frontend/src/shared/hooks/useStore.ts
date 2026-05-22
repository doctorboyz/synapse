import { create } from 'zustand'
import type { Document, Scope, Stats, SearchResult } from '../api/client'

interface AppState {
  documents: Document[]
  selectedDoc: Document | null
  scopes: Scope[]
  stats: Stats | null
  searchResults: SearchResult[]
  searchQuery: string
  isLoading: boolean
  error: string | null
  activeScope: string | null
  activeDocType: string | null
  setDocuments: (docs: Document[]) => void
  setSelectedDoc: (doc: Document | null) => void
  setScopes: (scopes: Scope[]) => void
  setStats: (stats: Stats) => void
  setSearchResults: (results: SearchResult[]) => void
  setSearchQuery: (q: string) => void
  setLoading: (v: boolean) => void
  setError: (e: string | null) => void
  setActiveScope: (s: string | null) => void
  setActiveDocType: (t: string | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  documents: [],
  selectedDoc: null,
  scopes: [],
  stats: null,
  searchResults: [],
  searchQuery: '',
  isLoading: false,
  error: null,
  activeScope: null,
  activeDocType: null,
  setDocuments: (docs) => set({ documents: docs || [] }),
  setSelectedDoc: (doc) => set({ selectedDoc: doc }),
  setScopes: (scopes) => set({ scopes: scopes || [] }),
  setStats: (stats) => set({ stats }),
  setSearchResults: (results) => set({ searchResults: results || [] }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setLoading: (v) => set({ isLoading: v }),
  setError: (e) => set({ error: e }),
  setActiveScope: (s) => set({ activeScope: s }),
  setActiveDocType: (t) => set({ activeDocType: t }),
}))
