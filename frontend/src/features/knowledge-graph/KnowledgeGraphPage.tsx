import { useEffect, useState, useMemo } from 'react'
import { Search, FileText, Layers, Clock, ArrowRight, ChevronLeft } from 'lucide-react'
import { useDocuments, useStats } from '../../shared/hooks/useDocuments'
import { useAppStore } from '../../shared/hooks/useStore'
import { Badge } from '../../shared/components/Badge'
import { Loading } from '../../shared/components/Loading'
import { EmptyState } from '../../shared/components/EmptyState'
import * as api from '../../shared/api/client'
import type { Document, TraceNode } from '../../shared/api/client'

export function KnowledgeGraphPage() {
  const { documents, isLoading, error, searchResults, searchQuery, activeScope, activeDocType } = useAppStore()
  const { load, search } = useDocuments()
  const { loadScopes, scopes } = useStats()
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null)
  const [traceChain, setTraceChain] = useState<TraceNode[]>([])
  const [view, setView] = useState<'list' | 'graph'>('list')

  useEffect(() => {
    load({
      scope: activeScope || undefined,
      doc_type: activeDocType || undefined,
    })
    loadScopes()
  }, [activeScope, activeDocType])

  const handleSearch = async (q: string) => {
    useAppStore.getState().setSearchQuery(q)
    if (!q.trim()) {
      useAppStore.getState().setSearchResults([])
      return
    }
    await search(q)
  }

  const selectDocument = async (doc: Document) => {
    setSelectedDoc(doc)
    try {
      const chain = await api.getTraceChain(doc.id)
      setTraceChain(chain)
    } catch {
      setTraceChain([])
    }
  }

  const displayDocs = searchQuery.trim() ? [] : (documents || [])
  const results = searchQuery.trim() ? (searchResults || []) : []

  // Debug logging
  useEffect(() => {
    console.log('[KG] docs count:', documents?.length, 'scope:', activeScope, 'type:', activeDocType)
  }, [documents, activeScope, activeDocType])

  const showDetailMobile = selectedDoc !== null

  return (
    <div className="flex h-full relative">
      {/* Left panel - List */}
      <div className={`flex-1 flex flex-col min-w-0 border-r border-[var(--color-border)] bg-[var(--color-surface-elevated)] md:bg-transparent
        ${showDetailMobile ? 'hidden md:flex' : 'flex'}
      `}>
        {/* Header */}
        <div className="p-5 border-b border-[var(--color-border)] bg-white">
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
              <input
                type="text"
                placeholder="Search knowledge..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:border-transparent"
              />
            </div>
            <div className="flex gap-1">
              <button
                onClick={() => setView('list')}
                className={`px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium transition-colors ${
                  view === 'list' ? 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                }`}
              >
                List
              </button>
              <button
                onClick={() => setView('graph')}
                className={`px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium transition-colors ${
                  view === 'graph' ? 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                }`}
              >
                Graph
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            <select
              value={activeScope || ''}
              onChange={(e) => useAppStore.getState().setActiveScope(e.target.value || null)}
              className="px-3 py-1.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-sm)] text-xs text-[var(--color-text-secondary)] focus:outline-none"
            >
              <option value="">All scopes</option>
              {(scopes || []).map((s) => (
                <option key={s.name} value={s.name}>{s.name} ({s.doc_count})</option>
              ))}
            </select>
            <select
              value={activeDocType || ''}
              onChange={(e) => useAppStore.getState().setActiveDocType(e.target.value || null)}
              className="px-3 py-1.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-sm)] text-xs text-[var(--color-text-secondary)] focus:outline-none"
            >
              <option value="">All types</option>
              <option value="note">Note</option>
              <option value="learning">Learning</option>
              <option value="retro">Retro</option>
            </select>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Debug banner - remove after fix */}
          {import.meta.env.DEV && (
            <div className="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800 font-mono">
              docs: {documents?.length ?? 'null'} | scope: {activeScope ?? 'none'} | type: {activeDocType ?? 'none'} | loading: {String(isLoading)} | error: {error ?? 'none'}
            </div>
          )}

          {isLoading && <Loading />}
          {error && (
            <div className="p-4 mb-4 bg-red-50 border border-red-200 rounded-[var(--radius-lg)]">
              <p className="text-sm text-red-700 font-medium">Failed to load documents</p>
              <p className="text-xs text-red-600 mt-1">{error}</p>
              <button
                onClick={() => load({ scope: activeScope || undefined, doc_type: activeDocType || undefined })}
                className="mt-2 px-3 py-1 bg-red-100 text-red-700 rounded-md text-xs hover:bg-red-200 transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {/* Debug / status bar */}
          {!isLoading && !error && (
            <div className="flex items-center justify-between mb-3 text-xs text-[var(--color-text-muted)]">
              <span>
                {activeScope ? `Scope: ${activeScope}` : 'All scopes'}
                {activeDocType ? ` · Type: ${activeDocType}` : ''}
                {' · '}
                {displayDocs.length} document{displayDocs.length !== 1 ? 's' : ''}
              </span>
              <button
                onClick={() => load({ scope: activeScope || undefined, doc_type: activeDocType || undefined })}
                className="px-2 py-1 rounded-md hover:bg-[var(--color-surface-elevated)] text-[var(--color-text-secondary)] transition-colors"
              >
                Refresh
              </button>
            </div>
          )}

          {/* Search results */}
          {searchQuery.trim() && results.length > 0 && (
            <div className="mb-4">
              <p className="text-xs text-[var(--color-text-muted)] mb-3">{results.length} results for "{searchQuery}"</p>
              <div className="space-y-2">
                {results.map((r) => (
                  <div
                    key={r.id}
                    onClick={async () => {
                      const doc = await api.getDocument(r.id)
                      selectDocument(doc)
                    }}
                    className="p-4 bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] cursor-pointer hover:border-[var(--color-accent)] hover:shadow-sm transition-all"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-medium text-[var(--color-text)] truncate">{r.title}</h4>
                        <p className="text-xs text-[var(--color-text-secondary)] mt-1 line-clamp-2">{r.content}</p>
                      </div>
                      <Badge variant="accent">{(r.score * 100).toFixed(0)}%</Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="muted">{r.scope}</Badge>
                      <Badge variant="muted">{r.doc_type}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {searchQuery.trim() && results.length === 0 && !isLoading && (
            <EmptyState title="No results" description={`No documents match "${searchQuery}"`} />
          )}

          {/* Document list or Graph */}
          {!searchQuery.trim() && displayDocs.length > 0 && view === 'list' && (
            <div className="space-y-2">
              {displayDocs.map((doc) => (
                <div
                  key={doc.id}
                  onClick={() => selectDocument(doc)}
                  className={`p-4 bg-white border rounded-[var(--radius-lg)] cursor-pointer hover:shadow-sm transition-all ${
                    selectedDoc?.id === doc.id
                      ? 'border-[var(--color-accent)] ring-1 ring-[var(--color-accent-subtle)]'
                      : 'border-[var(--color-border)] hover:border-[var(--color-border-strong)]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[var(--color-surface-elevated)] flex items-center justify-center shrink-0">
                      <FileText className="w-4 h-4 text-[var(--color-text-muted)]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-medium text-[var(--color-text)] truncate">{doc.title}</h4>
                      <p className="text-xs text-[var(--color-text-secondary)] mt-0.5 line-clamp-1">{doc.content?.slice(0, 120)}...</p>
                      <div className="flex items-center gap-2 mt-2">
                        <Badge variant="accent">{doc.doc_type}</Badge>
                        <Badge variant="muted">{doc.scope}</Badge>
                        {doc.source_project && <Badge variant="muted">{doc.source_project}</Badge>}
                        <span className="text-xs text-[var(--color-text-muted)] ml-auto">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Graph view */}
          {!searchQuery.trim() && displayDocs.length > 0 && view === 'graph' && (
            <GraphView
              docs={displayDocs}
              selected={selectedDoc}
              traceChain={traceChain}
              onSelect={selectDocument}
            />
          )}

          {!searchQuery.trim() && displayDocs.length === 0 && !isLoading && (
            <EmptyState title="No documents" description="Upload or sync documents to get started." />
          )}
        </div>
      </div>

      {/* Right panel - Detail */}
      <div
        className={`bg-white border-l border-[var(--color-border)] overflow-y-auto z-10
          md:w-96 md:static md:block
          ${showDetailMobile ? 'fixed inset-0 w-full block' : 'hidden'}
        `}
      >
        {selectedDoc ? (
          <div className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <button
                onClick={() => setSelectedDoc(null)}
                className="md:hidden p-1 rounded-md hover:bg-[var(--color-surface-elevated)] mr-1"
              >
                <ChevronLeft className="w-4 h-4 text-[var(--color-text-secondary)]" />
              </button>
              <Badge variant="accent">{selectedDoc.doc_type}</Badge>
              <Badge variant="muted">{selectedDoc.scope}</Badge>
            </div>

            <h2 className="text-lg font-semibold text-[var(--color-text)] mb-3">{selectedDoc.title}</h2>

            <div className="prose prose-sm max-w-none">
              <pre className="whitespace-pre-wrap text-sm text-[var(--color-text-secondary)] bg-[var(--color-surface-elevated)] p-4 rounded-[var(--radius-md)] border border-[var(--color-border)] font-sans leading-relaxed">
                {selectedDoc.content}
              </pre>
            </div>

            <div className="mt-5 space-y-3">
              <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
                <Clock className="w-3.5 h-3.5" />
                Created: {new Date(selectedDoc.created_at).toLocaleString()}
              </div>
              {selectedDoc.source_file && (
                <div className="text-xs text-[var(--color-text-muted)]">Source: {selectedDoc.source_file}</div>
              )}
            </div>

            {/* Trace chain */}
            {(traceChain || []).length > 0 && (
              <div className="mt-6">
                <h3 className="text-sm font-medium text-[var(--color-text)] mb-3 flex items-center gap-2">
                  <Layers className="w-4 h-4" />
                  Relationships
                </h3>
                <div className="space-y-2">
                  {(traceChain || []).map((node, i) => (
                    <div key={node.id} className="flex items-center gap-2">
                      <div className="flex flex-col items-center">
                        <div className="w-2 h-2 rounded-full bg-[var(--color-accent)]" />
                        {i < (traceChain || []).length - 1 && <div className="w-0.5 h-6 bg-[var(--color-border)]" />}
                      </div>
                      <div className="flex-1 p-2.5 bg-[var(--color-surface-elevated)] rounded-[var(--radius-md)] border border-[var(--color-border)]">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-[var(--color-text)]">{node.title}</span>
                          <Badge variant="accent">{node.relation}</Badge>
                        </div>
                        <div className="text-xs text-[var(--color-text-muted)] mt-1">
                          Confidence: {(node.confidence * 100).toFixed(0)}% · Depth: {node.depth}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--color-text-muted)]">
            <div className="text-center">
              <ArrowRight className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Select a document to view details</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── Graph View ─── */

function GraphView({
  docs,
  selected,
  traceChain,
  onSelect,
}: {
  docs: Document[]
  selected: Document | null
  traceChain: TraceNode[]
  onSelect: (doc: Document) => void
}) {
  const width = 900
  const height = Math.max(500, docs.length * 35)
  const [allTraces, setAllTraces] = useState<Map<string, TraceNode[]>>(new Map())
  const [showLabels, setShowLabels] = useState(true)

  const nodes = useMemo(() => {
    const cols = Math.max(3, Math.min(20, Math.ceil(Math.sqrt(docs.length * 1.5))))
    const spacingX = width / (cols + 1)
    const spacingY = Math.max(80, 140 - docs.length * 0.2)
    return docs.map((doc, i) => ({
      ...doc,
      x: ((i % cols) + 1) * spacingX,
      y: (Math.floor(i / cols) + 1) * spacingY,
    }))
  }, [docs])

  // Pre-load trace chains for all visible docs to draw graph edges
  useEffect(() => {
    if (docs.length === 0) return
    let cancelled = false
    // Batch trace loading to avoid flooding the API
    const BATCH_SIZE = 20
    async function loadAll() {
      const map = new Map<string, TraceNode[]>()
      for (let i = 0; i < docs.length; i += BATCH_SIZE) {
        if (cancelled) break
        const batch = docs.slice(i, i + BATCH_SIZE)
        const results = await Promise.all(
          batch.map(async (doc) => {
            try {
              const chain = await api.getTraceChain(doc.id)
              return { id: doc.id, chain }
            } catch {
              return { id: doc.id, chain: [] }
            }
          })
        )
        for (const r of results) {
          if (r.chain.length > 0) map.set(r.id, r.chain)
        }
        if (!cancelled) setAllTraces(new Map(map))
      }
    }
    loadAll()
    return () => { cancelled = true }
  }, [docs.map((d) => d.id).join(',')])

  const selectedNode = selected ? nodes.find((n) => n.id === selected.id) : null
  const nodeIds = useMemo(() => new Set(nodes.map((n) => n.id)), [nodes])

  // Build all edges from pre-loaded traces (only between visible nodes)
  const edges = useMemo(() => {
    const list: { source: typeof nodes[0]; target: typeof nodes[0]; relation: string; highlight: boolean }[] = []

    // Trace edges for all docs
    for (const [sourceId, chain] of allTraces.entries()) {
      const source = nodes.find((n) => n.id === sourceId)
      if (!source) continue
      for (const t of chain) {
        if (!nodeIds.has(t.id)) continue
        const target = nodes.find((n) => n.id === t.id)
        if (!target || source.id === target.id) continue
        list.push({
          source,
          target,
          relation: t.relation,
          highlight: selected?.id === source.id || selected?.id === target.id,
        })
      }
    }

    // Also add selected-node trace edges (may include nodes outside current view)
    if (selectedNode) {
      for (const t of traceChain) {
        const target = nodes.find((n) => n.id === t.id)
        if (!target) continue
        const existing = list.find((e) =>
          (e.source.id === selectedNode.id && e.target.id === target.id) ||
          (e.source.id === target.id && e.target.id === selectedNode.id)
        )
        if (!existing) {
          list.push({ source: selectedNode, target, relation: t.relation, highlight: true })
        }
      }
    }

    return list
  }, [nodes, allTraces, selectedNode, traceChain, selected])

  // Scope-group edges: light connections between docs in same scope
  const scopeEdges = useMemo(() => {
    const list: { source: typeof nodes[0]; target: typeof nodes[0] }[] = []
    const byScope: Record<string, typeof nodes> = {}
    for (const n of nodes) {
      byScope[n.scope] = byScope[n.scope] || []
      byScope[n.scope].push(n)
    }
    for (const group of Object.values(byScope)) {
      if (group.length < 2) continue
      for (let i = 0; i < group.length - 1; i++) {
        list.push({ source: group[i], target: group[i + 1] })
      }
    }
    return list
  }, [nodes])

  // Compute connection counts for bubble sizing
  const connectionCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    // Count visible-to-visible edges
    for (const e of edges) {
      counts[e.source.id] = (counts[e.source.id] || 0) + 1
      counts[e.target.id] = (counts[e.target.id] || 0) + 1
    }
    // Count ALL traces (including targets outside current view)
    for (const [sourceId, chain] of allTraces.entries()) {
      counts[sourceId] = (counts[sourceId] || 0) + chain.length
      for (const t of chain) {
        counts[t.id] = (counts[t.id] || 0) + 1
      }
    }
    // Also count scope edges as weaker connections
    for (const e of scopeEdges) {
      counts[e.source.id] = (counts[e.source.id] || 0) + 0.5
      counts[e.target.id] = (counts[e.target.id] || 0) + 0.5
    }
    return counts
  }, [edges, scopeEdges, allTraces])

  const maxConnections = Math.max(1, ...Object.values(connectionCounts))

  const nodeRadius = (nodeId: string, isSelected: boolean) => {
    if (isSelected) return 32
    const count = connectionCounts[nodeId] || 0
    // Scale from 18 (no connections) to 28 (max connections)
    return 18 + (count / maxConnections) * 10
  }

  const nodeColor = (docType: string) => {
    switch (docType) {
      case 'note': return '#0ea5e9'
      case 'learning': return '#8b5cf6'
      case 'retro': return '#f59e0b'
      case 'wisdom': return '#10b981'
      case 'reference': return '#6366f1'
      default: return '#94a3b8'
    }
  }

  return (
    <div className="w-full h-full overflow-auto bg-white rounded-[var(--radius-lg)] border border-[var(--color-border)] relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-full min-h-[400px]"
        style={{ cursor: 'grab' }}
      >
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="6" refX="20" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="var(--color-border-strong)" />
          </marker>
        </defs>

        {/* Scope group edges (very light) */}
        {scopeEdges.map((e, i) => (
          <line
            key={`scope-${i}`}
            x1={e.source.x}
            y1={e.source.y}
            x2={e.target.x}
            y2={e.target.y}
            stroke="#e2e8f0"
            strokeWidth={0.8}
            strokeDasharray="2 4"
          />
        ))}

        {/* Trace edges */}
        {edges.map((e, i) => {
          const mx = (e.source.x + e.target.x) / 2
          const my = (e.source.y + e.target.y) / 2
          const labelVisible = showLabels || e.highlight
          return (
            <g key={`trace-${i}`}>
              <line
                x1={e.source.x}
                y1={e.source.y}
                x2={e.target.x}
                y2={e.target.y}
                stroke={e.highlight ? 'var(--color-accent)' : '#94a3b8'}
                strokeWidth={e.highlight ? 2.5 : 1.2}
                strokeDasharray={e.highlight ? '0' : '4 2'}
                markerEnd="url(#arrow)"
                opacity={e.highlight ? 1 : 0.55}
              />
              {labelVisible && (
                <rect
                  x={mx - 22}
                  y={my - 12}
                  width={44}
                  height={14}
                  rx={3}
                  fill={e.highlight ? 'var(--color-accent)' : '#ffffff'}
                  opacity={0.9}
                />
              )}
              {labelVisible && (
                <text
                  x={mx}
                  y={my - 3}
                  textAnchor="middle"
                  fill={e.highlight ? '#ffffff' : '#64748b'}
                  fontSize={7}
                  fontWeight={600}
                >
                  {e.relation}
                </text>
              )}
            </g>
          )
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const isSelected = selected?.id === node.id
          const hasLinks = edges.some((e) => e.source.id === node.id || e.target.id === node.id)
          const r = nodeRadius(node.id, isSelected)
          const connCount = Math.round(connectionCounts[node.id] || 0)
          const nodeChain = allTraces.get(node.id) || []
          const hasExternalLinks = nodeChain.some((t) => !nodeIds.has(t.id))
          return (
            <g
              key={node.id}
              onClick={() => onSelect(node)}
              className="cursor-pointer"
              style={{ cursor: 'pointer' }}
            >
              <circle
                cx={node.x}
                cy={node.y}
                r={r}
                fill={isSelected ? 'var(--color-accent-subtle)' : '#ffffff'}
                stroke={nodeColor(node.doc_type)}
                strokeWidth={isSelected ? 3 : hasLinks ? 2.5 : 1.5}
                opacity={0.95}
              />
              {/* External link indicator — small dot when target is outside view */}
              {hasExternalLinks && (
                <circle
                  cx={node.x + r * 0.85}
                  cy={node.y + r * 0.5}
                  r={4}
                  fill="#f59e0b"
                  stroke="#ffffff"
                  strokeWidth={1}
                />
              )}
              {/* Connection count badge inside bubble */}
              {connCount > 0 && (
                <circle
                  cx={node.x + r * 0.7}
                  cy={node.y - r * 0.7}
                  r={8}
                  fill="var(--color-accent)"
                />
              )}
              {connCount > 0 && (
                <text
                  x={node.x + r * 0.7}
                  y={node.y - r * 0.7 + 3}
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize={8}
                  fontWeight={700}
                >
                  {connCount}
                </text>
              )}
              <text
                x={node.x}
                y={node.y - r - 10}
                textAnchor="middle"
                className="text-xs"
                fill="var(--color-text)"
                fontSize={11}
                fontWeight={500}
              >
                {node.title.slice(0, 18)}{node.title.length > 18 ? '...' : ''}
              </text>
              <text
                x={node.x}
                y={node.y + 4}
                textAnchor="middle"
                fill={nodeColor(node.doc_type)}
                fontSize={9}
                fontWeight={600}
              >
                {node.doc_type}
              </text>
            </g>
          )
        })}
      </svg>

      {docs.length > 0 && (
        <div className="absolute top-3 left-3 flex gap-3">
          <div className="bg-white/90 backdrop-blur-sm border border-[var(--color-border)] rounded-[var(--radius-md)] px-3 py-1.5 shadow-sm pointer-events-none">
            <p className="text-xs text-[var(--color-text-secondary)]">
              <span className="inline-block w-2 h-2 rounded-full bg-[#0ea5e9] mr-1" />note
            </p>
          </div>
          <div className="bg-white/90 backdrop-blur-sm border border-[var(--color-border)] rounded-[var(--radius-md)] px-3 py-1.5 shadow-sm pointer-events-none">
            <p className="text-xs text-[var(--color-text-secondary)]">
              <span className="inline-block w-2 h-2 rounded-full bg-[#8b5cf6] mr-1" />learning
            </p>
          </div>
          <div className="bg-white/90 backdrop-blur-sm border border-[var(--color-border)] rounded-[var(--radius-md)] px-3 py-1.5 shadow-sm pointer-events-none">
            <p className="text-xs text-[var(--color-text-secondary)]">
              <span className="inline-block w-2 h-2 rounded-full bg-[#f59e0b] mr-1" />retro
            </p>
          </div>
          <button
            onClick={() => setShowLabels((v) => !v)}
            className={`px-2.5 py-1 rounded-[var(--radius-md)] text-[10px] font-medium border shadow-sm transition-colors ${
              showLabels
                ? 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)] border-[var(--color-accent)]/20'
                : 'bg-white/90 text-[var(--color-text-muted)] border-[var(--color-border)] hover:text-[var(--color-text)]'
            }`}
          >
            {showLabels ? 'Hide labels' : 'Show labels'}
          </button>
        </div>
      )}

      {!selected && docs.length > 0 && (
        <div className="absolute bottom-3 right-3 pointer-events-none">
          <div className="bg-white/90 backdrop-blur-sm border border-[var(--color-border)] rounded-[var(--radius-md)] px-3 py-2 shadow-sm">
            <p className="text-xs text-[var(--color-text-muted)]">
              {edges.length} trace link{edges.length !== 1 ? 's' : ''} · {scopeEdges.length} scope group{scopeEdges.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
