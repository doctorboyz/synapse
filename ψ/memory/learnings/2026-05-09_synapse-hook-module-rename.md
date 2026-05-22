---
name: synapse-hook-module-rename
description: Module rename จาก synapse → src ทำให้ hook configuration ใน settings.json ชี้ไปยัง module ที่ไม่มีอยู่แล้ว
 type: project
---

## Lesson

เมื่อ rename/refactor module structure (เช่น `synapse/` → `src/`) ต้องจับทุก references รวมถึง:
- Hook commands ใน `~/.claude/settings.json`
- MCP server args
- Import paths ใน documentation
- CLI entry points

## Why

ในครั้งนี้ module `synapse.ingest.hook_handler` และ `synapse.mcp.server` ถูกย้ายไปอยู่ใน `src/` แต่ `settings.json` ยังเก็บ references เก่าไว้ ทำให้:
1. PostToolUse hook fail ทุกครั้งที่ edit/write ไฟล์
2. MCP server ไม่สามารถ start ได้
3. Auto-ingest feature ใช้งานไม่ได้

## How to apply

1. หลัง refactor module structure ให้ `grep` หาชื่อ module เก่าใน:
   - `~/.claude/settings.json` (hooks, mcpServers)
   - `pyproject.toml` (entry points)
   - ไฟล์ README / documentation
2. ใช้ `cd <project_root> && python -m src.module` แทน absolute path ถ้าเป็นไปได้
3. เพิ่ม validation step หลัง refactor: ลองรัน hook command ด้วยมือ 1 ครั้งเพื่อยืนยันว่าทำงานได้
4. ถ้าใช้ venv ให้ใช้ `sys.executable` หรือ `which python` จาก project context แทน hardcoded path
