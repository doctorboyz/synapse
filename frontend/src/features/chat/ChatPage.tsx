import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send, Bot, User, Loader2, ChevronDown, Filter,
  Plus, MessageSquare, Trash2, X, Menu, Clock,
} from 'lucide-react'
import { useStats } from '../../shared/hooks/useDocuments'
import * as api from '../../shared/api/client'
import type { SearchResult } from '../../shared/api/client'
import { Markdown } from '../../shared/components/Markdown'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SearchResult[]
  model?: string
}

interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  model: string
  scopes: string[]
  createdAt: number
  updatedAt: number
}

const STORAGE_KEY = 'synapse_chat_sessions'
const CURRENT_KEY = 'synapse_chat_current_id'
const LAST_MODEL_KEY = 'synapse_chat_last_model'

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    // Backward compat: old sessions had `scope: string` instead of `scopes: string[]`
    return parsed.map((s) => ({
      ...s,
      scopes: Array.isArray(s.scopes)
        ? s.scopes
        : s.scope
          ? [s.scope]
          : [],
    }))
  } catch {
    return []
  }
}

function saveSessions(sessions: ChatSession[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
}

function generateTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === 'user')
  if (firstUser) {
    const t = firstUser.content.slice(0, 40)
    return t.length < firstUser.content.length ? t + '...' : t
  }
  return 'New Chat'
}

export function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions)
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [models, setModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState('kimi-k2.6:cloud')
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [selectedScopes, setSelectedScopes] = useState<string[]>([])
  const [showScopeMenu, setShowScopeMenu] = useState(false)
  const [showSidebar, setShowSidebar] = useState(false)
  const [linkPopup, setLinkPopup] = useState<{ title: string; results: SearchResult[] } | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { loadScopes, scopes } = useStats()

  const handleObsidianLink = useCallback(async (title: string) => {
    try {
      const results = await api.search(title, { limit: 5 })
      setLinkPopup({ title, results: results.slice(0, 5) })
    } catch {
      setLinkPopup({ title, results: [] })
    }
  }, [])

  // Load models + scopes
  useEffect(() => {
    loadScopes()
    api.getOllamaModels().then((m) => {
      const modelsArr = Array.isArray(m) ? m : []
      const names = modelsArr.map((x) => x.name)
      setModels(names)
      const saved = localStorage.getItem(LAST_MODEL_KEY)
      if (saved && names.includes(saved)) {
        setSelectedModel(saved)
      } else if (names.length > 0) {
        setSelectedModel(names[0])
      }
    }).catch(() => {
      setModels([])
    })

    // Restore last active session
    const lastId = localStorage.getItem(CURRENT_KEY)
    if (lastId) {
      const s = loadSessions().find((x) => x.id === lastId)
      if (s) {
        setCurrentId(s.id)
        setMessages(s.messages)
        setSelectedModel(s.model)
        setSelectedScopes(s.scopes || [])
      }
    }
  }, [])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Close scope menu on outside click
  useEffect(() => {
    if (!showScopeMenu) return
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('.scope-menu-container')) {
        setShowScopeMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showScopeMenu])

  // Persist last model
  useEffect(() => {
    localStorage.setItem(LAST_MODEL_KEY, selectedModel)
  }, [selectedModel])

  // Auto-save current session
  const saveCurrent = useCallback((msgs: ChatMessage[]) => {
    if (!currentId) return
    setSessions((prev) => {
      const updated = prev.map((s) =>
        s.id === currentId
          ? {
              ...s,
              messages: msgs,
              title: generateTitle(msgs),
              updatedAt: Date.now(),
              model: selectedModel,
              scopes: selectedScopes,
            }
          : s
      )
      saveSessions(updated)
      return updated
    })
  }, [currentId, selectedModel, selectedScopes])

  useEffect(() => {
    if (currentId && messages.length > 0) {
      saveCurrent(messages)
    }
  }, [messages, saveCurrent])

  const startNewChat = () => {
    const newSession: ChatSession = {
      id: crypto.randomUUID(),
      title: 'New Chat',
      messages: [],
      model: selectedModel,
      scopes: selectedScopes,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    setSessions((prev) => {
      const updated = [newSession, ...prev]
      saveSessions(updated)
      return updated
    })
    setCurrentId(newSession.id)
    setMessages([])
    localStorage.setItem(CURRENT_KEY, newSession.id)
    setShowSidebar(false)
  }

  const loadSession = (session: ChatSession) => {
    setCurrentId(session.id)
    setMessages(session.messages)
    setSelectedModel(session.model)
    setSelectedScopes(session.scopes || [])
    localStorage.setItem(CURRENT_KEY, session.id)
    setShowSidebar(false)
  }

  const deleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    setSessions((prev) => {
      const updated = prev.filter((s) => s.id !== sessionId)
      saveSessions(updated)
      return updated
    })
    if (currentId === sessionId) {
      setCurrentId(null)
      setMessages([])
      localStorage.removeItem(CURRENT_KEY)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return

    // Auto-start new session if none active
    let activeId = currentId
    if (!activeId) {
      const newSession: ChatSession = {
        id: crypto.randomUUID(),
        title: input.trim().slice(0, 40),
        messages: [],
        model: selectedModel,
        scopes: selectedScopes,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      }
      setSessions((prev) => {
        const updated = [newSession, ...prev]
        saveSessions(updated)
        return updated
      })
      activeId = newSession.id
      setCurrentId(activeId)
      localStorage.setItem(CURRENT_KEY, activeId)
    }

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
    }

    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setIsLoading(true)

    let assistantContent = ''
    const assistantId = crypto.randomUUID()
    let sources: SearchResult[] = []

    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', model: selectedModel, sources: [] },
    ])

    try {
      await api.chatStream(
        userMsg.content,
        (chunk) => {
          assistantContent += chunk
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: assistantContent, sources }
                : m
            )
          )
        },
        { model: selectedModel, scopes: selectedScopes.length > 0 ? selectedScopes : undefined },
        (s) => {
          sources = s
          // Force re-render so sources appear even before first content chunk
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, sources: s }
                : m
            )
          )
        }
      )
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}` }
            : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (ts: number) => {
    const d = new Date(ts)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    if (isToday) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div
        className={`bg-[var(--color-surface-elevated)] border-r border-[var(--color-border)] flex flex-col
          md:w-64 md:static md:block md:translate-x-0
          fixed inset-y-0 left-0 z-30 w-72 transition-transform duration-300
          ${showSidebar ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Sidebar header */}
        <div className="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-[var(--color-accent)]" />
            <span className="font-medium text-[var(--color-text)] text-sm">Chat History</span>
          </div>
          <button
            onClick={() => setShowSidebar(false)}
            className="md:hidden p-1 rounded-md hover:bg-[var(--color-border)]"
          >
            <X className="w-4 h-4 text-[var(--color-text-secondary)]" />
          </button>
        </div>

        {/* New chat button */}
        <div className="p-3">
          <button
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-[var(--color-accent)] text-white rounded-[var(--radius-md)] text-sm font-medium hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        {/* Sessions list */}
        <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
          {sessions.length === 0 && (
            <div className="text-center py-8 text-[var(--color-text-muted)]">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-xs">No chat history yet</p>
              <p className="text-xs mt-1 opacity-60">Start a new conversation</p>
            </div>
          )}
          {sessions.map((session) => {
            const isActive = session.id === currentId
            const msgCount = session.messages.length
            return (
              <button
                key={session.id}
                onClick={() => loadSession(session)}
                className={`w-full text-left px-3 py-2.5 rounded-[var(--radius-md)] text-sm transition-colors group relative ${
                  isActive
                    ? 'bg-[var(--color-accent-subtle)] border border-[var(--color-accent)]'
                    : 'hover:bg-white border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2">
                  <MessageSquare className={`w-4 h-4 shrink-0 mt-0.5 ${isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-muted)]'}`} />
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium truncate ${isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-text)]'}`}>
                      {session.title}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-[var(--color-text-muted)]">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(session.updatedAt)}
                      </span>
                      <span>{msgCount} msg{msgCount !== 1 ? 's' : ''}</span>
                      {session.scopes && session.scopes.length > 0 && (
                        <span className="px-1.5 py-0.5 bg-[var(--color-border)] rounded text-[10px] truncate max-w-[80px]">
                          {session.scopes.length === 1 ? session.scopes[0] : `${session.scopes.length} scopes`}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => deleteSession(e, session.id)}
                    className={`p-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity ${
                      isActive ? 'hover:bg-[var(--color-accent)]/10' : 'hover:bg-[var(--color-border)]'
                    }`}
                    title="Delete chat"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-[var(--color-text-muted)] hover:text-red-500" />
                  </button>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Overlay for mobile sidebar */}
      {showSidebar && (
        <div
          className="fixed inset-0 bg-black/20 z-20 md:hidden"
          onClick={() => setShowSidebar(false)}
        />
      )}

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="px-5 py-3 border-b border-[var(--color-border)] bg-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(true)}
              className="md:hidden p-1.5 rounded-md hover:bg-[var(--color-surface-elevated)]"
            >
              <Menu className="w-5 h-5 text-[var(--color-text-secondary)]" />
            </button>
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-[var(--color-accent)]" />
              <span className="font-medium text-[var(--color-text)]">Synapse Chat</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Scope selector */}
            <div className="relative scope-menu-container">
              <button
                onClick={() => setShowScopeMenu(!showScopeMenu)}
                className="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              >
                <Filter className="w-3 h-3" />
                {selectedScopes.length === 0
                  ? 'All scopes'
                  : selectedScopes.length === 1
                    ? selectedScopes[0]
                    : `${selectedScopes.length} scopes`}
                <ChevronDown className="w-3 h-3" />
              </button>
              {showScopeMenu && (
                <div className="absolute right-0 mt-1 w-56 bg-white border border-[var(--color-border)] rounded-[var(--radius-md)] shadow-lg z-10 p-2">
                  <div className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider px-2 py-1">Select scopes</div>
                  <label className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-[var(--color-surface-elevated)]">
                    <input
                      type="checkbox"
                      checked={selectedScopes.length === 0}
                      onChange={() => setSelectedScopes([])}
                      className="accent-[var(--color-accent)]"
                    />
                    <span className="text-xs text-[var(--color-text)]">All scopes</span>
                  </label>
                  <div className="my-1 border-t border-[var(--color-border)]" />
                  {(scopes || []).map((s) => {
                    const checked = selectedScopes.includes(s.name)
                    return (
                      <label key={s.name} className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-[var(--color-surface-elevated)]">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            setSelectedScopes((prev) =>
                              checked
                                ? prev.filter((name) => name !== s.name)
                                : [...prev, s.name]
                            )
                          }}
                          className="accent-[var(--color-accent)]"
                        />
                        <span className="text-xs text-[var(--color-text-secondary)]">{s.name} ({s.doc_count})</span>
                      </label>
                    )
                  })}
                  <div className="mt-2 pt-2 border-t border-[var(--color-border)] flex justify-end">
                    <button
                      onClick={() => setShowScopeMenu(false)}
                      className="px-3 py-1 bg-[var(--color-accent)] text-white rounded text-[10px] font-medium hover:bg-[var(--color-accent-hover)]"
                    >
                      Done
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Model selector */}
            <div className="relative">
              <button
                onClick={() => setShowModelMenu(!showModelMenu)}
                className="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              >
                {selectedModel}
                <ChevronDown className="w-3 h-3" />
              </button>
              {showModelMenu && (
                <div className="absolute right-0 mt-1 w-48 bg-white border border-[var(--color-border)] rounded-[var(--radius-md)] shadow-lg z-10">
                  {(models || []).map((m) => (
                    <button
                      key={m}
                      onClick={() => { setSelectedModel(m); setShowModelMenu(false) }}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-[var(--color-surface-elevated)] first:rounded-t-[var(--radius-md)] last:rounded-b-[var(--radius-md)] ${
                        m === selectedModel ? 'text-[var(--color-accent)] font-medium' : 'text-[var(--color-text-secondary)]'
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {(messages || []).length === 0 && (
            <div className="flex items-center justify-center h-full text-[var(--color-text-muted)]">
              <div className="text-center">
                <Bot className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Ask anything about your knowledge vault</p>
                <p className="text-xs mt-1 opacity-60">Uses hybrid search + LLM synthesis</p>
              </div>
            </div>
          )}

          {(messages || []).map((msg) => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full bg-[var(--color-accent-subtle)] flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 text-[var(--color-accent)]" />
                </div>
              )}
              <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-first' : ''}`}>
                <div
                  className={`px-4 py-3 rounded-[var(--radius-lg)] text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-[var(--color-accent)] text-white'
                      : 'bg-white border border-[var(--color-border)] text-[var(--color-text)]'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <Markdown text={msg.content || ''} onObsidianLink={handleObsidianLink} />
                  ) : (
                    <div className="whitespace-pre-wrap">{msg.content || ' '}</div>
                  )}
                  {msg.model && (
                    <div className="mt-1.5 text-xs opacity-60">{msg.model}</div>
                  )}
                </div>
                {/* Source citations for assistant messages */}
                {msg.role === 'assistant' && (msg.sources || []).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <span className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider mr-1">Sources:</span>
                    {(msg.sources || []).map((src) => (
                      <span
                        key={src.id}
                        className="inline-flex items-center gap-1 px-2 py-0.5 bg-[var(--color-accent-subtle)] border border-[var(--color-accent)]/20 rounded-full text-[10px] text-[var(--color-accent)] cursor-pointer hover:bg-[var(--color-accent)]/10 transition-colors"
                        title={`${src.title} (${src.scope})`}
                      >
                        {src.title.slice(0, 25)}{src.title.length > 25 ? '...' : ''}
                        <span className="text-[var(--color-text-muted)]">·{src.scope}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-full bg-[var(--color-border-strong)] flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4 text-[var(--color-text-muted)]" />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Obsidian link popup */}
        {linkPopup && (
          <div className="absolute bottom-24 left-1/2 -translate-x-1/2 w-[360px] max-w-[90vw] bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] shadow-xl z-20">
            <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)]">
              <span className="text-xs font-medium text-[var(--color-text)]">{linkPopup.title}</span>
              <button onClick={() => setLinkPopup(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <X className="w-3 h-3" />
              </button>
            </div>
            <div className="p-2 max-h-48 overflow-y-auto">
              {linkPopup.results.length === 0 ? (
                <p className="text-xs text-[var(--color-text-muted)] px-2 py-2">No documents found</p>
              ) : (
                linkPopup.results.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => {
                      setInput(r.title)
                      setLinkPopup(null)
                    }}
                    className="w-full text-left px-2 py-1.5 rounded hover:bg-[var(--color-surface-elevated)] text-xs text-[var(--color-text)]"
                  >
                    <span className="font-medium">{r.title}</span>
                    <span className="text-[var(--color-text-muted)] ml-1">({r.scope})</span>
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="px-5 py-4 border-t border-[var(--color-border)] bg-white">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder="Ask a question..."
              disabled={isLoading}
              className="flex-1 px-4 py-2.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !input.trim()}
              className="px-4 py-2.5 bg-[var(--color-accent)] text-white rounded-[var(--radius-md)] hover:bg-[var(--color-accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
