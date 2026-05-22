---
name: no-ci-means-hidden-test-failures
description: Without CI, broken tests silently accumulate as technical debt
type: learning
---

# No CI Means Hidden Test Failures

**Date**: 2026-05-05
**Source**: synapse v3 — 16 V1 test files were broken with no one noticing
**Context**: V1 test fixtures were removed during v2→v3 migration, leaving 16 test files that import from `synapse.*` and fail with missing fixtures

## Lesson

If tests aren't run automatically (CI), broken tests become invisible debt. 16 V1 test files were broken for an unknown period with zero visibility. The test suite appeared to have high coverage but the actual runnable tests were much fewer.

**Why it matters**: Without CI, developers run tests locally only when they remember to. Broken tests don't block merges. Over time, the gap between "total test files" and "actually passing tests" grows silently.

**How to apply**: Set up CI (GitHub Actions) that runs the full test suite on every push. Consider adding test infrastructure (PostgreSQL service container, optional Qdrant service) so that even integration tests run automatically. Also, remove dead code directories (`synapse/`) that confuse new contributors about which package is active.

---

**Tags**: ci, testing, technical-debt, github-actions