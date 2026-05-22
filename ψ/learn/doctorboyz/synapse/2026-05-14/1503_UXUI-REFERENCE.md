# Synapse Frontend — UX/UI Reference Report

**Date:** 2026-05-14
**Scope:** `/Users/doctorboyz/code/github.com/doctorboyz/synapse/ψ/learn/doctorboyz/synapse/origin/frontend/src`
**Tech Stack:** React 19 + Tailwind CSS v4 + TypeScript + Vite + Lucide React

---

## 1. UI Component Inventory

| Component | File | Type | Reusability | Notes |
|-----------|------|------|-------------|-------|
| `Layout` | `src/shared/components/Layout.tsx` | Layout shell | High | Sidebar + main content wrapper with mobile overlay logic. Hardcodes nav items internally; not configurable via props. |
| `NavItem` | `src/shared/components/Layout.tsx:97` | Navigation link | Medium | Private to Layout. Uses `NavLink` from react-router-dom. No ARIA label support. |
| `Badge` | `src/shared/components/Badge.tsx` | Status label | High | 5 variants (`default`, `accent`, `success`, `warning`, `muted`). Clean prop API. |
| `Loading` | `src/shared/components/Loading.tsx` | Loading indicator | High | Simple spinner + text. No size variants. |
| `EmptyState` | `src/shared/components/EmptyState.tsx` | Empty placeholder | High | Icon + title + optional description. Uses generic `Inbox` icon for all contexts. |
| `ErrorBoundary` | `src/shared/components/ErrorBoundary.tsx` | Error fallback | High | Class component. Uses **inline styles** instead of Tailwind — breaks design system. |
| `Markdown` | `src/shared/components/Markdown.tsx` | Content renderer | Medium | Custom inline parser (not a library). Handles headings, lists, code blocks, links, Obsidian `[[links]]`. Risky regex-based parsing. |
| `GraphView` | `src/features/knowledge-graph/KnowledgeGraphPage.tsx:329` | Data visualization | Low | Large SVG-based graph with nodes, edges, labels. ~350 lines. No zoom/pan. Not reusable outside KG page. |
| Form inputs | Various page files | Primitive | N/A | Standard HTML inputs styled with Tailwind utility classes. No shared `Input`, `Textarea`, `Select`, or `Button` components. |

**Missing shared components:** `Button`, `Input`, `Textarea`, `Select`, `Modal`, `Toast`, `Skeleton`, `Tooltip`, `Dialog`, `ConfirmDialog`.

---

## 2. Design System Audit

### Tokens (defined in `src/index.css`)

| Token | Value | Usage |
|-------|-------|-------|
| `--color-surface` | `#ffffff` | Primary background |
| `--color-surface-elevated` | `#f8fafc` | Secondary background, input bg |
| `--color-border` | `#e2e8f0` | Default borders |
| `--color-border-strong` | `#cbd5e1` | Hover/active borders |
| `--color-text` | `#0f172a` | Primary text |
| `--color-text-secondary` | `#475569` | Secondary text |
| `--color-text-muted` | `#94a3b8` | Muted/disabled text |
| `--color-accent` | `#0ea5e9` | Primary action color |
| `--color-accent-hover` | `#0284c7` | Hover state |
| `--color-accent-subtle` | `#e0f2fe` | Subtle highlight bg |
| `--color-success` | `#10b981` | **Unused in tokens — only defined** |
| `--color-warning` | `#f59e0b` | **Unused in tokens — only defined** |
| `--color-error` | `#ef4444` | **Unused in tokens — only defined** |
| `--radius-sm` | `6px` | Small badges, inputs |
| `--radius-md` | `10px` | Buttons, cards, nav items |
| `--radius-lg` | `14px` | Large cards, panels |

### Inconsistencies Found

1. **CommandsPage ignores the entire design system** (`src/features/commands/CommandsPage.tsx`)
   - Hardcoded dark theme: `bg-[#0f172a]`, `bg-[#1e293b]`, `text-emerald-400`, `text-slate-200`.
   - Uses arbitrary Tailwind values and its own color palette instead of theme variables.
   - Creates a jarring visual break when navigating from any other page.

2. **ErrorBoundary uses inline styles** (`src/shared/components/ErrorBoundary.tsx:30-58`)
   - Hardcodes `#ef4444`, `#f8fafc`, `8px`, `16px` — completely bypasses Tailwind and theme tokens.
   - No dark mode awareness. Button uses raw hex instead of `var(--color-accent)`.

3. **Badge variant colors drift from tokens** (`src/shared/components/Badge.tsx:11-12`)
   - `success` uses `bg-emerald-50 text-emerald-600` (Tailwind defaults, not theme vars).
   - `warning` uses `bg-amber-50 text-amber-600`.
   - These do not match the `--color-success` / `--color-warning` tokens defined in `index.css`.

4. **GraphView node colors are hardcoded** (`src/features/knowledge-graph/KnowledgeGraphPage.tsx:478-487`)
   - `#0ea5e9`, `#8b5cf6`, `#f59e0b`, `#10b981`, `#6366f1`, `#94a3b8` — raw hex values.
   - Should map to theme tokens or a centralized color map.

5. **Dead CSS remains in `App.css`** (`src/App.css`)
   - `.counter`, `.hero`, `#center`, `#next-steps`, `#docs`, `#spacer`, `.ticks` — all leftover Vite/React starter template styles.
   - `var(--accent)`, `var(--accent-bg)`, `var(--accent-border)` referenced but **never defined** in `index.css`.

6. **No design token for shadows**
   - `shadow-sm` and `shadow-lg` used arbitrarily from Tailwind defaults.
   - No unified elevation scale.

7. **No typography scale**
   - Font sizes are ad-hoc: `text-xs`, `text-sm`, `text-base`, `text-lg`, `text-2xl`.
   - No `--font-size-*` tokens or consistent line-height rules.

---

## 3. Accessibility Review (WCAG 2.1 AA)

### Failures

| Issue | Severity | File | Line | Details |
|-------|----------|------|------|---------|
| **GraphView nodes are not keyboard-accessible** | Critical | `KnowledgeGraphPage.tsx` | 570-638 | `<g>` elements with `onClick` lack `role="button"`, `tabIndex`, and `onKeyDown`. Completely unreachable via keyboard. |
| **Icon-only buttons lack `aria-label`** | High | `Layout.tsx` | 46, 80, 259 | Mobile menu toggle, sidebar close, detail back button — all icon-only with no accessible name. |
| **View toggle buttons lack `aria-label`** | High | `KnowledgeGraphPage.tsx` | 76-91 | "List" / "Graph" buttons rely on visible text, but no `aria-pressed` state for toggle semantics. |
| **Scope/type `<select>` elements lack `<label>`** | High | `KnowledgeGraphPage.tsx` | 97-116 | Two `<select>` filters have no associated `<label>`; placeholder text inside options is not sufficient. |
| **No skip-to-content link** | Medium | `Layout.tsx` | N/A | Keyboard users must tab through entire sidebar nav to reach main content. |
| **Chat delete button lacks confirmation + `aria-label`** | Medium | `ChatPage.tsx` | 383-391 | Trash icon button has `title="Delete chat"` (mouse-only) but no `aria-label`. Deletes immediately with no confirmation dialog. |
| **Model selector dropdown lacks `aria-expanded`** | Medium | `ChatPage.tsx` | 484-506 | Custom dropdown pattern missing `role="listbox"`, `aria-expanded`, `aria-haspopup`. |
| **Scope menu checkboxes lack grouping** | Medium | `ChatPage.tsx` | 438-479 | Checkbox list inside a popup has no `role="group"` or `aria-labelledby`. |
| **No `prefers-reduced-motion` support** | Medium | Global | N/A | `animate-spin` on loaders, `transition-transform` on menus, `duration-200/300` everywhere. No `@media (prefers-reduced-motion: reduce)` overrides. |
| **ErrorBoundary `<pre>` has no `tabIndex`** | Low | `ErrorBoundary.tsx` | 33-45 | Stack trace may overflow; not scrollable via keyboard. |
| **Mobile overlay lacks `role="dialog"` or `aria-modal`** | Low | `Layout.tsx` | 24-28 | Sidebar overlay is just a `<div>` with `onClick`. |

### Passes

- Viewport meta tag present (`index.html:6`).
- `lang="en"` set on `<html>`.
- Focus rings are generally present (`focus:ring-2 focus:ring-[var(--color-accent)]`).
- Color contrast for text on surface appears acceptable (slate-900 on white, slate-500 on white).
- Chat message bubbles have sufficient contrast (white text on `#0ea5e9`).

### Touch Target Sizes

| Element | Size | WCAG 2.1 Target (44x44) | Status |
|---------|------|------------------------|--------|
| Sidebar close (mobile) | ~28x28 (`p-1` + icon) | Fail | Too small |
| Mobile hamburger | ~36x36 (`p-1.5` + icon) | Fail | Too small |
| Nav items | ~40px tall (`py-2.5`) | Marginal | Acceptable width, height slightly under |
| Detail back button | ~28x28 | Fail | Too small |
| Graph node labels | Variable | N/A | SVG text is not a touch target |
| Tab buttons (PushPage) | ~40px tall | Marginal | Slightly under 44px |
| Chat send button | ~40px tall | Marginal | Slightly under 44px |

---

## 4. Visual Hierarchy

### Heading Structure

| Page | h1 | h2 | h3 | h4 | Notes |
|------|----|----|----|-----|-------|
| KnowledgeGraphPage | No | No | Yes (detail title) | Yes (list item titles) | Missing page-level heading. Search/filter bar has no heading. |
| PushPage | Yes (`text-2xl`) | No | No | No | Good single h1. |
| ChatPage | No | No | No | No | No headings at all. Relies on spans and visual weight. |
| CommandsPage | No | No | No | No | Terminal aesthetic; no semantic headings. |

**Issues:**
- Two pages lack any `<h1>`, violating document outline best practices.
- KnowledgeGraph detail panel uses `<h2>` for document title but the list items use `<h4>` without intermediate `<h3>` — heading levels skip.
- Markdown component maps `# ` to `<h3>`, `## ` to `<h4>`, `### ` to `<h5>` — this is intentionally offset, but may confuse screen reader users if the surrounding page already has its own heading structure.

### Font Size Distribution

| Token | Size | Used For |
|-------|------|----------|
| `text-[10px]` | 10px | Scope count badges, button labels, dropdown headers |
| `text-xs` | 12px | Metadata, timestamps, form hints, chat sources |
| `text-sm` | 14px | Body text, inputs, buttons, nav labels, list items |
| `text-base` | 16px | Markdown h3, default (rarely used) |
| `text-lg` | 18px | Detail panel document title |
| `text-2xl` | 24px | PushPage h1 only |

**Assessment:** The scale is functional but narrow. There is no `text-xl` or `text-3xl+` usage, limiting expressive hierarchy. The gap between `text-sm` (14px) and `text-lg` (18px) is large — no intermediate step for subheadings.

### Weight Distribution

- `font-medium` (500) used for: nav items, active states, button text, list titles, badges.
- `font-semibold` (600) used for: page titles, detail headings, section headers.
- `font-bold` (700) rarely used (only connection count badge in graph).

**Assessment:** Reasonable differentiation, but `font-medium` is overused — nearly everything is medium weight, reducing the impact of semibold headings.

---

## 5. Interaction Patterns

### Loading States

| Component | Pattern | Assessment |
|-----------|---------|------------|
| `Loading` | Spinner + text | Good, consistent. Used in KG page and hooks. |
| Data fetching | Boolean flag + spinner | No skeleton screens; content pops in abruptly. |
| Chat streaming | Progressive text render | Excellent. Real-time chunk rendering with source citation injection. |
| File upload | "Uploading..." button text | Acceptable. No progress bar. |
| GraphView trace loading | Silent background batching | No visible loading state while edges load. Users may think graph is incomplete. |

### Empty States

| Context | Implementation | Assessment |
|---------|---------------|------------|
| No documents | `EmptyState` component | Good. Generic but functional. |
| No search results | `EmptyState` component | Good. Includes the query string. |
| No chat history | Inline icon + text | Acceptable. Different from `EmptyState` component — inconsistent. |
| No command history | Inline icon + text | Acceptable. Different pattern again. |
| Detail panel empty | Inline icon + "Select a document" | Acceptable but not using `EmptyState`. |

### Error States

| Context | Implementation | Assessment |
|---------|---------------|------------|
| API error (KG page) | Red banner with Retry button | Good. Inline, contextual, actionable. |
| API error (hooks) | `console.error` only | Bad. Errors in `useStats` and `useDocuments` are logged but not always surfaced to UI. |
| Global error | `ErrorBoundary` | Poor. Ugly inline-styled fallback. No "Try again" or route recovery. |
| Chat error | Inline error message in assistant bubble | Good. Keeps conversation context. |
| Push error | Inline result banner | Good. Green/red distinction is clear. |

### Transitions & Animations

| Element | Transition | Assessment |
|---------|-----------|------------|
| Mobile sidebar | `duration-200 ease-out` slide | Good. Backdrop fade would improve perceived speed. |
| Chat sidebar | `duration-300` slide | Slightly slow; okay. |
| Button hover | `transition-colors` | Good, subtle. |
| Card hover | `hover:shadow-sm transition-all` | Good. |
| Graph node hover | None | Missing. Nodes are clickable but give no hover feedback. |
| Dropdown menus | None (instant) | Acceptable but could use `opacity + scale` micro-transition. |
| Loading spinner | `animate-spin` | Standard. No reduced-motion alternative. |

### Micro-interactions

- **Copy button in CommandsPage:** Appears on group hover (`opacity-0 group-hover:opacity-100`). Good discoverability pattern.
- **Chat delete button:** Appears on group hover. Hidden by default, revealed on hover. Problematic for touch devices (no hover).
- **File drop zone:** Border and background color change on drag. Good.
- **Suggest scope button:** Sparkles icon + disabled state. Clear affordance.

---

## 6. Mobile & Responsive

### Viewport & Safe Areas

- `viewport` meta tag: `width=device-width, initial-scale=1.0` — present. Missing `viewport-fit=cover` for notched devices.
- No `env(safe-area-inset-*)` usage. Content may overlap home indicators on iOS.

### Breakpoints

The codebase uses a single breakpoint: **`md:` (768px)**.

| Pattern | Below 768px | Above 768px |
|---------|-------------|-------------|
| Layout sidebar | Fixed overlay, hidden by default | Static inline, always visible |
| Knowledge Graph detail | Fixed fullscreen overlay | Static 384px side panel |
| Commands help grid | 1 column | 3 columns |
| PushPage content | Full width with `p-4` | Centered `max-w-2xl` with `p-8` |
| Chat sidebar | Fixed overlay | Static inline |

**Issues:**
- No `sm:` (640px) or `lg:` (1024px) refinements. Layout jumps directly from mobile to desktop at 768px.
- GraphView SVG has a fixed `width={900}` (`KnowledgeGraphPage.tsx:340`). On screens narrower than 900px, the SVG overflows its container. It has `overflow-auto` on the wrapper, but horizontal scrolling on a graph is poor UX.
- The detail panel on mobile (`fixed inset-0 w-full`) lacks a close affordance other than the small back arrow. Users may not know how to exit.

### Touch-Friendly Sizing

- Most buttons are `px-4 py-2` or larger — acceptable.
- Icon-only buttons (menu toggle, close, back, delete) are frequently `p-1` or `p-1.5` — too small for reliable touch targeting.
- Select dropdowns and inputs are full-width on mobile — good.
- Chat input area is fixed at bottom — good, stays accessible.

---

## 7. UX Defects

| # | Defect | Severity | File | Line | Evidence |
|---|--------|----------|------|------|----------|
| 1 | **Graph nodes completely inaccessible to keyboard/screen readers** | Critical | `KnowledgeGraphPage.tsx` | 570-638 | `<g onClick>` with no `role`, `tabIndex`, `aria-label`, or keyboard handler. |
| 2 | **CommandsPage is a visual alien — hardcoded dark theme breaks consistency** | High | `CommandsPage.tsx` | 164-260 | Uses `#0f172a`, `#1e293b`, `emerald-400` instead of theme tokens. |
| 3 | **Search input debounced? No — fires on every keystroke** | High | `KnowledgeGraphPage.tsx` | 67-72 | `onChange={(e) => handleSearch(e.target.value)}` with no `useDebounce`. Causes API spam. |
| 4 | **Chat session deletion has no confirmation** | High | `ChatPage.tsx` | 201-213 | `deleteSession` removes from localStorage immediately. One misclick = data loss. |
| 5 | **ErrorBoundary fallback is unstyled and off-brand** | High | `ErrorBoundary.tsx` | 27-63 | Inline styles, raw hex colors, no design system alignment. |
| 6 | **No skeleton loaders — content pops in** | Medium | Global | N/A | All data fetch transitions go from blank/spinner to fully rendered content. Jarring. |
| 7 | **GraphView overflows horizontally on small screens** | Medium | `KnowledgeGraphPage.tsx` | 340 | Fixed `width={900}` SVG. Mobile users must scroll horizontally. |
| 8 | **Mobile detail panel lacks obvious close action** | Medium | `KnowledgeGraphPage.tsx` | 248-265 | Only a small `<ChevronLeft>` arrow. No "Close" text or swipe-to-dismiss. |
| 9 | **Chat delete button invisible on touch devices** | Medium | `ChatPage.tsx` | 383-391 | `opacity-0 group-hover:opacity-100` — no hover on touch. Users cannot delete sessions on mobile. |
| 10 | **App.css contains dead starter styles** | Low | `App.css` | 1-184 | `.hero`, `.counter`, `#next-steps`, etc. Unused, shipped to production. |
| 11 | **No toast/notification system** | Low | Global | N/A | Success/error feedback is inline and page-specific. No global notification for background ops. |
| 12 | **GraphView trace loading is silent** | Low | `KnowledgeGraphPage.tsx` | 357-384 | Batch loads traces in background. No spinner or progress indicator. |
| 13 | **Markdown parser regex may fail on edge cases** | Low | `Markdown.tsx` | 131-192 | Custom regex parser for inline markdown. Vulnerable to nested patterns and could produce invalid React keys. |
| 14 | **No confirmation for `Clear` in CommandsPage** | Low | `CommandsPage.tsx` | 171-177 | Clears entire terminal history with one click. No undo. |

---

## 8. Recommendations

### Critical (Fix Immediately)

1. **Add keyboard/ARIA support to GraphView nodes**
   - Add `role="button"`, `tabIndex={0}`, `aria-label={`View ${node.title}`}`, and `onKeyDown` (Enter/Space) to each `<g>`.
   - Alternatively, render invisible `<button>` elements overlaid on nodes for native keyboard behavior.

2. **Debounce the search input**
   - Wrap `handleSearch` in a `useDebounce` hook (e.g., 300ms) to prevent API flooding.
   - File: `KnowledgeGraphPage.tsx:67-72`.

### High Impact

3. **Unify CommandsPage with the design system**
   - Replace all hardcoded slate/emerald colors with theme tokens.
   - If a dark terminal aesthetic is intentional, implement it via a `theme="dark"` prop on Layout or a dedicated dark-mode token set, not one-off hex values.

4. **Add delete confirmation to ChatPage**
   - Show a small inline confirmation ("Delete? Yes / No") or a shared `ConfirmDialog` component before removing sessions.

5. **Rewrite ErrorBoundary with Tailwind**
   - Remove inline styles. Use `className` with theme variables and standard spacing tokens.
   - Add a "Go Home" link in addition to "Reload".

6. **Add `aria-label` to all icon-only buttons**
   - Mobile menu toggles, sidebar close, detail back, chat delete, copy button.

### Medium Impact

7. **Create a `Skeleton` component and use it for data loading**
   - Skeleton cards for document list, skeleton lines for chat messages, skeleton stats for sidebar.

8. **Fix GraphView mobile overflow**
   - Make SVG responsive: `viewBox` already set, but remove fixed `width={900}` and use `width="100%"` with `preserveAspectRatio`.
   - Add zoom/pan controls (e.g., d3-zoom or native scroll + pinch).

9. **Add visible close affordance to mobile detail panel**
   - "Close" text next to the back arrow, or a swipe-to-dismiss gesture.

10. **Fix touch-only delete in ChatPage**
    - Make delete button always visible on mobile (`md:opacity-0 md:group-hover:opacity-100`), or use a long-press context menu.

11. **Add `<label>` elements to all `<select>` and `<input>` fields**
    - Scope filter, doc type filter, model selector. Use `htmlFor` + `id` association.

### Polish

12. **Remove dead CSS from `App.css`**
    - Delete all starter styles. Keep only project-specific global rules.

13. **Standardize empty states**
    - Use the `EmptyState` component everywhere (Chat history, Commands, Detail panel).

14. **Add `prefers-reduced-motion` support**
    - Disable `animate-spin` and `transition-transform` when user prefers reduced motion.

15. **Create shared primitive components**
    - `Button` (with `variant`, `size`, `isLoading`), `Input`, `Textarea`, `Select`, `Modal`.
    - Reduces duplication and ensures consistency.

16. **Add a toast/notification system**
    - For background operations: file upload complete, scope suggestion applied, etc.

17. **Unify Badge colors with theme tokens**
    - Replace `bg-emerald-50 text-emerald-600` with `bg-[var(--color-success)]/10 text-[var(--color-success)]`.

---

## Summary

The Synapse frontend is a functional React + Tailwind application with a clean, minimal aesthetic. The **Knowledge Graph page** and **Chat page** demonstrate solid UX thinking (streaming, progressive loading, inline search). However, the codebase suffers from:

- **Accessibility gaps** (keyboard-inaccessible graph, missing labels, no reduced-motion support)
- **Design system leakage** (CommandsPage hardcoded theme, ErrorBoundary inline styles, Badge color drift)
- **Mobile rough edges** (small touch targets, invisible touch actions, graph overflow)
- **Missing primitives** (no shared Button/Input/Modal/Skeleton components)

Priority order: fix critical accessibility (graph keyboard support) → add search debounce → unify CommandsPage styling → add delete confirmations → implement skeleton loading → polish remaining items.
