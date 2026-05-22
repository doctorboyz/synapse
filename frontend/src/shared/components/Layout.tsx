import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Database, Upload, MessageSquare, Sparkles, Menu, X, Terminal } from 'lucide-react'
import { useStats } from '../hooks/useDocuments'
import { useEffect, useState } from 'react'

export function Layout() {
  const { load, loadScopes, stats } = useStats()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    load()
    loadScopes()
  }, [])

  // Close mobile menu on route change
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="flex h-screen bg-[var(--color-surface-elevated)] relative">
      {/* Mobile overlay */}
      {menuOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40 md:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`bg-white border-r border-[var(--color-border)] flex flex-col z-50
          fixed inset-y-0 left-0 w-64 transform transition-transform duration-200 ease-out
          md:relative md:translate-x-0 md:w-60
          ${menuOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="p-5 border-b border-[var(--color-border)] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[var(--color-accent)] flex items-center justify-center">
              <Sparkles className="w-4.5 h-4.5 text-white" />
            </div>
            <span className="font-semibold text-[var(--color-text)] text-lg tracking-tight">Synapse</span>
          </div>
          <button
            onClick={() => setMenuOpen(false)}
            className="md:hidden p-1 rounded-md hover:bg-[var(--color-surface-elevated)]"
          >
            <X className="w-5 h-5 text-[var(--color-text-secondary)]" />
          </button>
        </div>

        {stats && (
          <div className="px-5 py-2 border-b border-[var(--color-border)]">
            <p className="text-xs text-[var(--color-text-muted)]">
              {stats.total_documents} docs · {Object.keys(stats.by_scope || {}).length} scopes
            </p>
          </div>
        )}

        <nav className="flex-1 p-3 space-y-1">
          <NavItem to="/" icon={<Database className="w-4.5 h-4.5" />} label="Knowledge Graph" />
          <NavItem to="/push" icon={<Upload className="w-4.5 h-4.5" />} label="Push" />
          <NavItem to="/chat" icon={<MessageSquare className="w-4.5 h-4.5" />} label="Chat" />
          <NavItem to="/commands" icon={<Terminal className="w-4.5 h-4.5" />} label="Commands" />
        </nav>

        <div className="p-4 border-t border-[var(--color-border)]">
          <div className="text-xs text-[var(--color-text-muted)]">
            Synapse v3 · Local-first
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col min-w-0">
        {/* Mobile header */}
        <div className="md:hidden bg-white border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-3 shrink-0">
          <button
            onClick={() => setMenuOpen(true)}
            className="p-1.5 rounded-md hover:bg-[var(--color-surface-elevated)]"
          >
            <Menu className="w-5 h-5 text-[var(--color-text-secondary)]" />
          </button>
          <span className="font-semibold text-[var(--color-text)]">Synapse</span>
        </div>

        <div className="flex-1 overflow-hidden">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-[var(--radius-md)] text-sm font-medium transition-colors ${
          isActive
            ? 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]'
            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-text)]'
        }`
      }
    >
      {icon}
      {label}
    </NavLink>
  )
}
