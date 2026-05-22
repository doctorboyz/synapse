import { useState, useRef, useEffect } from 'react'
import { Terminal, Send, Trash2, Copy, Check } from 'lucide-react'
import * as api from '../../shared/api/client'

interface CommandOutput {
  id: string
  command: string
  result: unknown
  error?: string
  timestamp: Date
}

const COMMAND_HELP: Record<string, { args: string; desc: string; level: 'global' | 'scope' | 'file' }> = {
  stats: { args: '', desc: 'Show vault statistics', level: 'global' },
  scopes: { args: '', desc: 'List all scopes', level: 'global' },
  projects: { args: '', desc: 'List registered projects', level: 'global' },
  search: { args: '"query" [--scope SCOPE]', desc: 'Search documents', level: 'scope' },
  list: { args: '[--scope SCOPE] [--limit N]', desc: 'List documents', level: 'scope' },
  get: { args: '<doc-id>', desc: 'Get document by ID', level: 'file' },
  'trace-chain': { args: '<doc-id>', desc: 'Show document trace chain', level: 'file' },
  concepts: { args: '[--search QUERY]', desc: 'List concepts', level: 'scope' },
  push: { args: '--title "..." --content "..." [--scope SCOPE]', desc: 'Push a document', level: 'scope' },
}

function parseArgs(input: string): Record<string, string | boolean> & { _positional?: string[] } {
  const args: Record<string, string | boolean> & { _positional?: string[] } = {}
  const tokens = input.trim().split(/\s+/)
  let i = 0
  while (i < tokens.length) {
    const tok = tokens[i]
    if (tok.startsWith('--')) {
      const key = tok.slice(2)
      if (i + 1 < tokens.length && !tokens[i + 1].startsWith('--')) {
        args[key] = tokens[i + 1]
        i += 2
      } else {
        args[key] = true
        i += 1
      }
    } else if (tok.startsWith('-')) {
      const key = tok.slice(1)
      if (i + 1 < tokens.length && !tokens[i + 1].startsWith('-')) {
        args[key] = tokens[i + 1]
        i += 2
      } else {
        args[key] = true
        i += 1
      }
    } else {
      if (!args._positional) args._positional = []
      args._positional.push(tok)
      i += 1
    }
  }
  return args
}

export function CommandsPage() {
  const [history, setHistory] = useState<CommandOutput[]>([])
  const [input, setInput] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const runCommand = async () => {
    const raw = input.trim()
    if (!raw || isRunning) return

    setIsRunning(true)
    setInput('')

    const spaceIdx = raw.indexOf(' ')
    const cmd = spaceIdx > 0 ? raw.slice(0, spaceIdx) : raw
    const rest = spaceIdx > 0 ? raw.slice(spaceIdx + 1) : ''
    const args = parseArgs(rest)
    const positional = (args._positional as string[] | undefined) || []

    let result: unknown = null
    let error: string | undefined

    try {
      switch (cmd) {
        case 'stats':
          result = await api.getStats()
          break
        case 'scopes':
          result = await api.getScopes()
          break
        case 'projects':
          result = await api.getProjects()
          break
        case 'search': {
          const query = positional[0] || (args.q as string) || ''
          if (!query) throw new Error('Usage: search "query" [--scope SCOPE]')
          result = await api.search(query, {
            scope: (args.scope as string) || undefined,
            limit: parseInt((args.limit as string) || '10'),
          })
          break
        }
        case 'list': {
          const data = await api.getDocuments({
            scope: (args.scope as string) || undefined,
            limit: parseInt((args.limit as string) || '20'),
          })
          result = data.documents
          break
        }
        case 'get': {
          const id = positional[0]
          if (!id) throw new Error('Usage: get <doc-id>')
          result = await api.getDocument(id)
          break
        }
        case 'trace-chain': {
          const id = positional[0]
          if (!id) throw new Error('Usage: trace-chain <doc-id>')
          result = await api.getTraceChain(id)
          break
        }
        case 'concepts': {
          // Backend has /concepts but client doesn't expose it yet; fallback
          result = { info: 'concepts endpoint not yet wired in client' }
          break
        }
        case 'push': {
          const title = (args.title as string) || positional[0]
          const content = (args.content as string) || positional[1]
          if (!title || !content) throw new Error('Usage: push --title "..." --content "..." [--scope SCOPE]')
          result = await api.pushDocument({ title, content, scope: (args.scope as string) || 'shared' })
          break
        }
        default:
          error = `Unknown command: ${cmd}. Type a command and press Enter. Supported: ${Object.keys(COMMAND_HELP).join(', ')}`
      }
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }

    setHistory((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        command: raw,
        result,
        error,
        timestamp: new Date(),
      },
    ])
    setIsRunning(false)
  }

  const copyResult = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1500)
  }

  return (
    <div className="flex flex-col h-full bg-[#0f172a]">
      {/* Header */}
      <div className="px-5 py-3 border-b border-slate-700 bg-[#1e293b] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-emerald-400" />
          <span className="font-medium text-slate-200">Synapse CLI</span>
        </div>
        <button
          onClick={() => setHistory([])}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-md transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Clear
        </button>
      </div>

      {/* Help */}
      <div className="px-5 py-3 border-b border-slate-700 bg-[#1e293b]/50">
        <p className="text-xs text-slate-400 mb-2">Available commands:</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          {Object.entries(COMMAND_HELP).map(([name, info]) => (
            <div key={name} className="text-xs">
              <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
                info.level === 'global' ? 'bg-purple-400' :
                info.level === 'scope' ? 'bg-blue-400' : 'bg-amber-400'
              }`} />
              <span className="text-emerald-400 font-mono">{name}</span>
              <span className="text-slate-500 ml-1">{info.args}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Output */}
      <div className="flex-1 overflow-y-auto px-5 py-4 font-mono text-sm space-y-4">
        {history.length === 0 && (
          <div className="text-slate-500 text-center py-10">
            <Terminal className="w-8 h-8 mx-auto mb-3 opacity-30" />
            <p>Type a command below and press Enter</p>
          </div>
        )}

        {history.map((entry) => (
          <div key={entry.id} className="space-y-1">
            <div className="flex items-center gap-2 text-slate-400">
              <span className="text-emerald-400">$</span>
              <span className="text-slate-200">{entry.command}</span>
              <span className="text-xs text-slate-600 ml-auto">
                {entry.timestamp.toLocaleTimeString()}
              </span>
            </div>
            {entry.error ? (
              <div className="text-red-400 bg-red-950/30 p-3 rounded-md border border-red-900/50">
                {entry.error}
              </div>
            ) : (
              <div className="relative group">
                <pre className="bg-[#1e293b] p-3 rounded-md border border-slate-700 text-slate-300 overflow-x-auto whitespace-pre-wrap text-xs leading-relaxed">
                  {JSON.stringify(entry.result, null, 2)}
                </pre>
                <button
                  onClick={() => copyResult(entry.id, JSON.stringify(entry.result, null, 2))}
                  className="absolute top-2 right-2 p-1.5 rounded-md bg-slate-700/80 text-slate-400 hover:text-slate-200 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  {copiedId === entry.id ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-5 py-4 border-t border-slate-700 bg-[#1e293b] shrink-0">
        <div className="flex gap-2">
          <span className="text-emerald-400 font-mono text-sm pt-2.5">$</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && runCommand()}
            placeholder={'search "async" --scope synapse'}
            disabled={isRunning}
            className="flex-1 px-3 py-2 bg-[#0f172a] border border-slate-700 rounded-md text-sm text-slate-200 font-mono focus:outline-none focus:border-emerald-500 placeholder:text-slate-600 disabled:opacity-50"
          />
          <button
            onClick={runCommand}
            disabled={isRunning || !input.trim()}
            className="px-4 py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
