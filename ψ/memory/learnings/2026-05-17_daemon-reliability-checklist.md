---
name: daemon-reliability-checklist
description: Non-negotiable daemon lifecycle requirements that must exist before a service is considered production-ready
type: feedback
---

## Rule: Every background service must have PID file + graceful error handling + restart policy before shipping.

**Why:** Synapse daemon "หายบ่อย" because three basics were missing: (1) `OllamaEmbedder()` crashed on boot without try/except, (2) no PID file meant `synapse status` always reported "not running", (3) Docker had no restart policy so container deaths were permanent. These are not advanced features — they are daemon hygiene.

**How to apply:** Before calling any service "done", verify:
- [ ] `write_pid()` on startup + `remove_pid()` on shutdown
- [ ] Every external dependency (DB, vector store, embedder, LLM) wrapped in try/except with degraded-mode fallback
- [ ] Docker-compose has `restart: unless-stopped` or `always`
- [ ] `/health` endpoint checks all critical dependencies
- [ ] Every scheduled/cron job writes to an audit log table, not just stdout
