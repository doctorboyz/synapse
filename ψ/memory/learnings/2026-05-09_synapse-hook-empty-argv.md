---
name: "Empty CLI arg handling in hook_handler"
description: "Shell env vars piped as CLI args can be empty strings. Always validate content, not just presence. Non-blocking hooks should exit 0 silently when context is missing."
type: feedback
---

**Rule:** When parsing CLI arguments from shell/env vars, validate the string content is non-empty, not just that the argument exists.

**Why:** In this session, `$CLAUDE_CODE_FILEPATH` was empty when the PostToolUse hook triggered after `Edit`. The shell passed `""` as `sys.argv[1]`, which passed `len(sys.argv) > 1` but was semantically invalid. The handler then errored with `"no file_path provided"` even though the argument was technically present.

**How to apply:**
- Replace `if len(sys.argv) > 1:` with `if len(sys.argv) > 1 and sys.argv[1]:`
- For non-blocking additive hooks (auto-ingest, logging, metrics), missing context should be a silent skip (exit 0), not an error (exit 1)
- If you need to distinguish "missing" from "empty", check both conditions explicitly

**Applies to:** Any Python script called as a Claude Code hook or shell command where env vars are interpolated into argv.
