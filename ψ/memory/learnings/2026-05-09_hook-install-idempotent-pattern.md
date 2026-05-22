---
name: hook-install-idempotent-pattern
type: learning
source: rrr: synapse
date: 2026-05-09
tags: [hooks, settings-json, idempotency, auto-ingest, context-injection]
---

# Hook Installation Must Be Idempotent and Marker-Based

## Context

When installing Claude Code hooks into `~/.claude/settings.json`, multiple runs of the installer should not create duplicate entries. Exact-match comparison is fragile because timeout values, matcher strings, and command paths can change over time.

## Lesson

Use **marker strings** embedded in hook commands as identity keys, not exact-match comparison. Each hook has a unique marker (e.g., `src.ingest.hook_handler` for ingest, `synapse-context-inject` for context). The installer searches for these markers in existing hook entries. If found, skip; if not, append.

This approach:
- Survives changes to timeout, matcher, or command arguments
- Never reorders existing hooks (append-only is safe)
- Works even if the user has manually edited their settings.json

## Pattern

```python
MARKER = "src.ingest.hook_handler"

def find_hook_entry(hooks_list, marker):
    for entry in hooks_list:
        for hook in entry.get("hooks", []):
            if marker in hook.get("command", ""):
                return entry
    return None
```

## Anti-Pattern

Do NOT compare full JSON objects. Do NOT remove and re-add hooks. Do NOT assume hook order matters.

---

## Bash Beats Python for PreToolUse Context Injection

PreToolUse hooks fire on every matching tool call (Read/Glob/Grep can be hundreds per session). Python startup adds ~200ms per invocation. A bash script using `kill -0` for PID checking runs in ~5ms — a 40x improvement. Only use Python for hooks that need database access (like the PostToolUse ingest hook).

---

## Vault Data Can Disappear Silently

A PostgreSQL restart or test teardown can wipe the vault without any notification. Always re-run `synapse init` after database recreation, and consider adding a vault health check command (`synapse health`) that compares current doc count against a known baseline.