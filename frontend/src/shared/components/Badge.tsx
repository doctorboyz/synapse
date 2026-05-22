interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'accent' | 'success' | 'warning' | 'muted'
  className?: string
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  const variants = {
    default: 'bg-[var(--color-surface-elevated)] text-[var(--color-text-secondary)]',
    accent: 'bg-[var(--color-accent-subtle)] text-[var(--color-accent)]',
    success: 'bg-emerald-50 text-emerald-600',
    warning: 'bg-amber-50 text-amber-600',
    muted: 'bg-transparent text-[var(--color-text-muted)] border border-[var(--color-border)]',
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-[var(--radius-sm)] text-xs font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  )
}
