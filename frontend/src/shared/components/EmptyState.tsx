import { Inbox } from 'lucide-react'

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-[var(--color-surface-elevated)] flex items-center justify-center mb-3">
        <Inbox className="w-5 h-5 text-[var(--color-text-muted)]" />
      </div>
      <h3 className="text-sm font-medium text-[var(--color-text-secondary)]">{title}</h3>
      {description && (
        <p className="text-xs text-[var(--color-text-muted)] mt-1 max-w-xs">{description}</p>
      )}
    </div>
  )
}
