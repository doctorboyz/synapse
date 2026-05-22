---
name: deep-learning-reveals-hidden-bugs
description: Mock tests reveal bugs that integration tests miss when external services are always None
type: learning
---

# Deep Learning Reveals Hidden Bugs

**Date**: 2026-05-05
**Source**: synapse v3 /learn --deep + test fixes
**Context**: QdrantStore.search() accepted `source_project` and `concepts` parameters but never used them in filter construction

## Lesson

When an external service (Qdrant, Ollama) is always set to `None` in tests, its code paths are never exercised. This hides bugs like unused parameters. Mock tests that actually call the methods with controlled inputs are essential for catching these issues.

**Why it matters**: In Synapse, Qdrant was `None` in all tests, so `search()` was never tested with real filters. The `source_project` and `concepts` parameters were silently ignored — a bug that would cause incorrect search results in production.

**How to apply**: For any service that's optionally None in tests, also write mock tests that exercise the full method signature with all parameters. This is separate from integration tests.

---

**Tags**: testing, mock, qdrant, hidden-bugs, coverage