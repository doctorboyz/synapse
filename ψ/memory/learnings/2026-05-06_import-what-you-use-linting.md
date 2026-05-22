# Lesson Learned: Import What You Use — Linting Catches NameErrors Instantly

**Date**: 2026-05-06
**Source**: rrr: synapse
**Context**: `_cmd_status` had `from src.cli import get_components, output` but used `cleanup` in the finally block, causing NameError at runtime

## Pattern

Writing `from src.cli import get_components, output` when the function body uses `cleanup` from the same module. This is a classic copy-paste error — I wrote the import line first, then added the finally block with `cleanup` later, but never went back to update the import.

The bug was only caught during manual testing (`synapse status` would crash). Static analysis tools like ruff, pyflakes, or pyright would have flagged this instantly as an undefined name.

## Why It Happened

No linter is configured for this project. The pyproject.toml has dev dependencies (pytest, pytest-asyncio, pytest-cov, testcontainers) but no linter. Python doesn't enforce imports at module load time for locally-defined names, so the NameError only surfaces at runtime when the specific code path is executed.

## How to Apply

- Add ruff to dev dependencies and CI pipeline
- Run `ruff check src/` before marking any task complete
- Consider a pre-commit hook or PostToolUse hook that runs `ruff check` on edited .py files
- The synapse project should add: `ruff>=0.4.0` to `[project.optional-dependencies.dev]`

## Tags

linting, ruff, imports, NameError, CI, quality