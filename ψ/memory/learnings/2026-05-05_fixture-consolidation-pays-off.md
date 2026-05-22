---
name: fixture-consolidation-pays-off
description: Consolidating shared test fixtures into conftest.py reduces duplication and enables new test types
type: learning
---

# Fixture Consolidation Pays Off

**Date**: 2026-05-05
**Source**: synapse v3 test refactor
**Context**: 3 files had overlapping pg_store, clean_pg, and component fixtures

## Lesson

When test fixtures are duplicated across files, adding a new test type (like API route tests) requires deciding which fixture to copy — creating more duplication. Consolidating into conftest.py breaks this cycle and makes the test suite more maintainable.

**Why it matters**: In Synapse, `pg_store`, `clean_pg`, and `app_components` were duplicated across conftest.py, test_mcp_server.py, and test_push.py. Adding API route tests would have required yet another copy. Consolidating into conftest with proper dependencies (push depends on clean_pg + qdrant_store + embedder) made adding `api_client` fixture trivial.

**How to apply**: When you see fixtures duplicated in 2+ test files, immediately consolidate into conftest.py. Also add convenience fixtures that compose simpler ones (e.g., `api_client` that depends on `clean_pg` + `init_routes`).

---

**Tags**: testing, conftest, fixtures, maintainability