interface MarkdownProps {
  text: string
  onObsidianLink?: (title: string) => void
}

export function Markdown({ text, onObsidianLink }: MarkdownProps) {
  // Simple inline markdown renderer
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let keyIdx = 0
  let inCode = false
  let codeLines: string[] = []

  const flushCode = () => {
    if (codeLines.length > 0) {
      elements.push(
        <pre
          key={keyIdx++}
          className="bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-[var(--radius-md)] p-3 my-2 overflow-x-auto text-xs leading-relaxed"
        >
          <code className="text-[var(--color-text)]">{codeLines.join('\n')}</code>
        </pre>
      )
      codeLines = []
    }
  }

  for (const raw of lines) {
    const line = raw.replace(/\r/g, '')

    if (line.startsWith('```')) {
      if (inCode) {
        flushCode()
        inCode = false
      } else {
        inCode = true
      }
      continue
    }

    if (inCode) {
      codeLines.push(line)
      continue
    }

    // Empty line
    if (!line.trim()) {
      elements.push(<div key={keyIdx++} className="h-2" />)
      continue
    }

    // Heading
    if (line.startsWith('# ')) {
      elements.push(
        <h3 key={keyIdx++} className="text-base font-semibold text-[var(--color-text)] mt-3 mb-1">
          {parseInline(line.slice(2))}
        </h3>
      )
      continue
    }
    if (line.startsWith('## ')) {
      elements.push(
        <h4 key={keyIdx++} className="text-sm font-semibold text-[var(--color-text)] mt-2 mb-1">
          {parseInline(line.slice(3))}
        </h4>
      )
      continue
    }
    if (line.startsWith('### ')) {
      elements.push(
        <h5 key={keyIdx++} className="text-xs font-semibold text-[var(--color-text)] mt-2 mb-1">
          {parseInline(line.slice(4))}
        </h5>
      )
      continue
    }

    // Bullet list
    if (line.trimStart().startsWith('- ') || line.trimStart().startsWith('* ')) {
      const content = line.trimStart().slice(2)
      elements.push(
        <li key={keyIdx++} className="ml-4 text-sm text-[var(--color-text)] list-disc">
          {parseInline(content)}
        </li>
      )
      continue
    }

    // Numbered list
    const numMatch = line.trimStart().match(/^(\d+)\.\s+(.*)/)
    if (numMatch) {
      elements.push(
        <li key={keyIdx++} className="ml-4 text-sm text-[var(--color-text)] list-decimal">
          {parseInline(numMatch[2])}
        </li>
      )
      continue
    }

    // Blockquote
    if (line.trimStart().startsWith('> ')) {
      elements.push(
        <blockquote
          key={keyIdx++}
          className="border-l-2 border-[var(--color-accent)] pl-3 my-1 text-sm text-[var(--color-text-secondary)] italic"
        >
          {parseInline(line.trimStart().slice(2))}
        </blockquote>
      )
      continue
    }

    // Horizontal rule
    if (line.trim() === '---' || line.trim() === '***') {
      elements.push(<hr key={keyIdx++} className="my-3 border-[var(--color-border)]" />)
      continue
    }

    // Paragraph
    elements.push(
      <p key={keyIdx++} className="text-sm text-[var(--color-text)] leading-relaxed my-1">
        {parseInline(line)}
      </p>
    )
  }

  flushCode()
  return <div className="markdown">{elements}</div>
}

function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  let remaining = text
  let idx = 0

  const patterns: { regex: RegExp; wrap: (...args: string[]) => React.ReactNode }[] = [
    { regex: /\*\*(.+?)\*\*/g, wrap: (s: string) => <strong key={idx++} className="font-semibold">{s}</strong> },
    { regex: /\*(.+?)\*/g, wrap: (s: string) => <em key={idx++} className="italic">{s}</em> },
    { regex: /`([^`]+)`/g, wrap: (s: string) => <code key={idx++} className="bg-[var(--color-surface-elevated)] px-1 py-0.5 rounded text-[11px] border border-[var(--color-border)]">{s}</code> },
    { regex: /\[([^\]]+)\]\(([^)]+)\)/g, wrap: (label: string, href: string) => <a key={idx++} href={href} target="_blank" rel="noopener noreferrer" className="text-[var(--color-accent)] underline hover:opacity-80">{label}</a> },
    {
      regex: /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
      wrap: (target: string, display: string) => {
        const label = (display || target).trim()
        const t = target.trim()
        return (
          <span
            key={idx++}
            className="text-[var(--color-accent)] cursor-pointer underline hover:opacity-80"
            onClick={() => onObsidianLink?.(t)}
            title={`Search: ${t}`}
          >
            {label}
          </span>
        )
      },
    },
  ]

  // Find earliest match
  while (remaining.length > 0) {
    let earliest: { index: number; length: number; result: RegExpExecArray; pattern: (typeof patterns)[number] } | null = null

    for (const pattern of patterns) {
      pattern.regex.lastIndex = 0
      const m = pattern.regex.exec(remaining)
      if (m && (!earliest || m.index < earliest.index)) {
        earliest = { index: m.index, length: m[0].length, result: m, pattern }
      }
    }

    if (!earliest) {
      parts.push(remaining)
      break
    }

    if (earliest.index > 0) {
      parts.push(remaining.slice(0, earliest.index))
    }

    const m = earliest.result
    if (m.length >= 3 && m[2] !== undefined) {
      parts.push(earliest.pattern.wrap(m[1], m[2]))
    } else {
      parts.push(earliest.pattern.wrap(m[1]))
    }

    remaining = remaining.slice(earliest.index + earliest.length)
  }

  return parts
}
