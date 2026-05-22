---
name: Auto-extract metadata at ingestion boundaries
---

## Rule

Always auto-extract metadata (concepts, tags, links) from content at ingestion boundaries. Don't require callers to manually pass extracted data.

**Why:** The `concepts` parameter in `push_text()` was always `None` because no caller ever extracted hashtags. Adding `extract_concepts(content)` as a default when `concepts=None` fixed the bug with zero caller changes and ensured all future pushes get concept extraction automatically.

**How to apply:** When a feature depends on data that can be derived from input content, derive it at the boundary function rather than expecting callers to pre-process. This is especially true for ingestion pipelines where content arrives from many sources (CLI, API, file scan, hooks) and callers shouldn't need to know about extraction rules.

---

## Rule

Frontend async callbacks that update local variables must also trigger state updates.

**Why:** The chat `onSources` callback updated a `sources` variable but didn't call `setMessages`, so citation badges never rendered until the first content chunk arrived (or never, if the stream ended first). Adding `setMessages((prev) => prev.map(...))` inside `onSources` made sources visible immediately.

**How to apply:** In React, any callback that receives async data should either: (a) store it in state directly, or (b) if it updates a local ref/variable, also trigger a re-render. When using `useState` + streaming, every data arrival point needs its own state pathway.

---

## Rule

Patch the module where the function is defined, not where it's imported.

**Why:** `startup()` does `from src.registry import restore_registry_backup` locally inside the function. Patching `src.main.restore_registry_backup` fails because the name isn't bound in `src.main` namespace. The correct patch target is `src.registry.restore_registry_backup`.

**How to apply:** When a function is imported locally (inside another function), patch the *source module* not the *consumer module*. Check the import statement's module path before writing the patch target.
