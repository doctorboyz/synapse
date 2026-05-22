import { useState, useCallback, useEffect } from 'react'
import { Type, FileUp, Globe, Check, AlertCircle, Video, Sparkles } from 'lucide-react'
import { useStats } from '../../shared/hooks/useDocuments'
import * as api from '../../shared/api/client'

 type Tab = 'text' | 'file' | 'website' | 'youtube'

interface UploadResult {
  id: string
  status: string
  error?: string
}

export function PushPage() {
  const [activeTab, setActiveTab] = useState<Tab>('text')
  const [scope, setScope] = useState('shared')
  const [customScope, setCustomScope] = useState('')
  const [isCustom, setIsCustom] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const { loadScopes, scopes } = useStats()

  useEffect(() => {
    loadScopes()
  }, [])

  const handleScopeChange = (value: string) => {
    if (value === '__custom__') {
      setIsCustom(true)
      setScope(customScope || 'shared')
    } else {
      setIsCustom(false)
      setScope(value)
    }
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'text', label: 'Text', icon: <Type className="w-4 h-4" /> },
    { id: 'file', label: 'File', icon: <FileUp className="w-4 h-4" /> },
    { id: 'website', label: 'Website', icon: <Globe className="w-4 h-4" /> },
    { id: 'youtube', label: 'YouTube', icon: <Video className="w-4 h-4" /> },
  ]

  const reset = () => {
    setResult(null)
    setIsSubmitting(false)
  }

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-[var(--color-text)] mb-2">Push Knowledge</h1>
        <p className="text-sm text-[var(--color-text-secondary)]">Push documents to your synapse vault</p>
      </div>

      {/* Scope selector */}
      <div className="mb-6 flex items-center gap-3 flex-wrap">
        <label className="text-sm text-[var(--color-text-secondary)]">Scope:</label>
        <div className="flex items-center gap-2">
          <select
            value={isCustom ? '__custom__' : scope}
            onChange={(e) => handleScopeChange(e.target.value)}
            className="px-3 py-1.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          >
            <option value="shared">shared (general knowledge)</option>
            {(scopes || []).map((s) => (
              <option key={s.name} value={s.name}>{s.name} ({s.doc_count} docs)</option>
            ))}
            <option value="__custom__">Custom...</option>
          </select>
          {isCustom && (
            <input
              type="text"
              value={customScope}
              onChange={(e) => {
                setCustomScope(e.target.value)
                setScope(e.target.value)
              }}
              placeholder="Enter scope name"
              className="px-3 py-1.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
            />
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[var(--color-surface-elevated)] p-1 rounded-[var(--radius-lg)] overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => { setActiveTab(tab.id); reset() }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-[var(--radius-md)] text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-white text-[var(--color-text)] shadow-sm'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Form */}
      <div className="bg-white border border-[var(--color-border)] rounded-[var(--radius-lg)] p-6">
        {activeTab === 'text' && (
          <TextUploadForm
            scope={scope}
            isSubmitting={isSubmitting}
            setIsSubmitting={setIsSubmitting}
            onResult={setResult}
            scopes={scopes || []}
            onScopeChange={(s) => {
              setIsCustom(false)
              setScope(s)
            }}
          />
        )}
        {activeTab === 'file' && (
          <FileUploadForm scope={scope} isSubmitting={isSubmitting} setIsSubmitting={setIsSubmitting} onResult={setResult} />
        )}
        {activeTab === 'website' && (
          <WebsiteUploadForm scope={scope} isSubmitting={isSubmitting} setIsSubmitting={setIsSubmitting} onResult={setResult} />
        )}
        {activeTab === 'youtube' && (
          <YoutubeUploadForm scope={scope} isSubmitting={isSubmitting} setIsSubmitting={setIsSubmitting} onResult={setResult} />
        )}
      </div>

      {/* Result */}
      {result && (
        <div className={`mt-4 p-4 rounded-[var(--radius-lg)] border flex items-center gap-3 ${
          result.error
            ? 'bg-red-50 border-red-200 text-red-700'
            : 'bg-emerald-50 border-emerald-200 text-emerald-700'
        }`}>
          {result.error ? <AlertCircle className="w-5 h-5" /> : <Check className="w-5 h-5" />}
          <div>
            <p className="text-sm font-medium">{result.error || `Uploaded successfully (ID: ${result.id.slice(0, 8)})`}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function TextUploadForm({
  scope,
  isSubmitting,
  setIsSubmitting,
  onResult,
  scopes,
  onScopeChange,
}: {
  scope: string
  isSubmitting: boolean
  setIsSubmitting: (v: boolean) => void
  onResult: (r: UploadResult) => void
  scopes: api.Scope[]
  onScopeChange: (s: string) => void
}) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [isSuggesting, setIsSuggesting] = useState(false)

  const submit = async () => {
    if (!title.trim() || !content.trim()) return
    setIsSubmitting(true)
    try {
      const res = await api.pushDocument({ title, content, scope })
      onResult({ id: res.id, status: 'success' })
      setTitle('')
      setContent('')
    } catch (err) {
      onResult({ id: '', status: 'error', error: err instanceof Error ? err.message : 'Upload failed' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const suggestScope = async () => {
    if (!title.trim() && !content.trim()) return
    setIsSuggesting(true)
    try {
      const combined = `${title}\n\n${content}`.slice(0, 4000)
      const available = scopes.map((s) => s.name)
      const res = await api.suggestScope(combined, available)
      if (res.scope) {
        onScopeChange(res.scope)
      }
    } catch {
      // ignore
    } finally {
      setIsSuggesting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-[var(--color-text)] mb-1.5">Title</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Enter document title..."
          className="w-full px-3 py-2.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-[var(--color-text)] mb-1.5">Content</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Enter content..."
          rows={8}
          className="w-full px-3 py-2.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] resize-none"
        />
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={submit}
          disabled={isSubmitting || !title.trim() || !content.trim()}
          className="px-5 py-2.5 bg-[var(--color-accent)] text-white rounded-[var(--radius-md)] text-sm font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? 'Uploading...' : 'Upload'}
        </button>
        <button
          onClick={suggestScope}
          disabled={isSuggesting || (!title.trim() && !content.trim())}
          className="flex items-center gap-1.5 px-4 py-2.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-[var(--color-text-secondary)] rounded-[var(--radius-md)] text-sm hover:text-[var(--color-accent)] hover:border-[var(--color-accent)] disabled:opacity-50 transition-colors"
          title="AI will suggest the best scope based on content"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {isSuggesting ? 'Suggesting...' : 'Suggest scope'}
        </button>
      </div>
    </div>
  )
}

function FileUploadForm({
  scope,
  isSubmitting,
  setIsSubmitting,
  onResult,
}: {
  scope: string
  isSubmitting: boolean
  setIsSubmitting: (v: boolean) => void
  onResult: (r: UploadResult) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0])
  }, [])

  const submit = async () => {
    if (!file) return
    setIsSubmitting(true)
    try {
      const res = await api.uploadFile(file, scope)
      onResult({ id: res.id, status: 'success' })
      setFile(null)
    } catch (err) {
      onResult({ id: '', status: 'error', error: err instanceof Error ? err.message : 'Upload failed' })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => document.getElementById('file-input')?.click()}
        className={`border-2 border-dashed rounded-[var(--radius-lg)] p-8 text-center cursor-pointer transition-colors ${
          isDragging
            ? 'border-[var(--color-accent)] bg-[var(--color-accent-subtle)]'
            : 'border-[var(--color-border)] hover:border-[var(--color-border-strong)]'
        }`}
      >
        <FileUp className="w-8 h-8 mx-auto mb-2 text-[var(--color-text-muted)]" />
        <p className="text-sm text-[var(--color-text-secondary)]">
          {file ? file.name : 'Drop file here or click to browse'}
        </p>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">Supports PDF, DOCX, TXT, MD</p>
        <input
          id="file-input"
          type="file"
          accept=".pdf,.docx,.txt,.md"
          onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
          className="hidden"
        />
      </div>
      <button
        onClick={submit}
        disabled={isSubmitting || !file}
        className="px-5 py-2.5 bg-[var(--color-accent)] text-white rounded-[var(--radius-md)] text-sm font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? 'Uploading...' : 'Upload'}
      </button>
    </div>
  )
}

function WebsiteUploadForm({
  scope,
  isSubmitting,
  setIsSubmitting,
  onResult,
}: {
  scope: string
  isSubmitting: boolean
  setIsSubmitting: (v: boolean) => void
  onResult: (r: UploadResult) => void
}) {
  const [url, setUrl] = useState('')

  const submit = async () => {
    if (!url.trim()) return
    setIsSubmitting(true)
    try {
      const res = await api.ingestWebsite(url, scope)
      onResult({ id: res.id, status: 'success' })
      setUrl('')
    } catch (err) {
      onResult({ id: '', status: 'error', error: err instanceof Error ? err.message : 'Scrape failed' })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-[var(--color-text)] mb-1.5">URL</label>
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            className="flex-1 px-3 py-2.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          />
          <button
            onClick={submit}
            disabled={isSubmitting || !url.trim()}
            className="px-5 py-2.5 bg-[var(--color-accent)] text-white rounded-[var(--radius-md)] text-sm font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? 'Scraping...' : 'Scrape'}
          </button>
        </div>
      </div>
    </div>
  )
}

function YoutubeUploadForm({
  scope,
  isSubmitting,
  setIsSubmitting,
  onResult,
}: {
  scope: string
  isSubmitting: boolean
  setIsSubmitting: (v: boolean) => void
  onResult: (r: UploadResult) => void
}) {
  const [url, setUrl] = useState('')

  const submit = async () => {
    if (!url.trim()) return
    setIsSubmitting(true)
    try {
      const res = await api.ingestYoutube(url, scope)
      onResult({ id: res.id, status: 'success' })
      setUrl('')
    } catch (err) {
      onResult({ id: '', status: 'error', error: err instanceof Error ? err.message : 'Transcript failed' })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-[var(--color-text)] mb-1.5">YouTube URL</label>
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            className="flex-1 px-3 py-2.5 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          />
          <button
            onClick={submit}
            disabled={isSubmitting || !url.trim()}
            className="px-5 py-2.5 bg-[var(--color-accent)] text-white rounded-[var(--radius-md)] text-sm font-medium hover:bg-[var(--color-accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? 'Processing...' : 'Get Transcript'}
          </button>
        </div>
      </div>
    </div>
  )
}
