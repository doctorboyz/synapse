"""Hook handler — auto-push on file writes

PostToolUse hook for Claude Code: auto-index knowledge directory writes
"""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from synapse.exceptions import ScopeError

log = logging.getLogger("synapse.ingest.hook")


def should_process(file_path: str) -> bool:
    """Check if file should be auto-indexed."""
    if not file_path:
        return False

    # Only process knowledge files
    triggers = [
        "/memory/learnings/",
        "/memory/retrospectives/",
        "/learnings/",
        "/retrospectives/",
    ]

    return any(t in file_path for t in triggers) and file_path.endswith(".md")


def detect_scope(file_path: str) -> str:
    """Auto-detect scope from file path using project directory patterns.

    Uses the same PROJECT_PATTERNS as scope/manager.py.
    """
    from synapse.scope.manager import PROJECT_PATTERNS

    for pattern in PROJECT_PATTERNS:
        match = pattern.search(file_path)
        if match:
            return match.group(1)
    return "shared"


def process_file(file_path: str) -> dict:
    """Process a file: index to synapse vault."""
    path = Path(file_path)
    if not path.exists():
        return {"status": "file_not_found", "path": file_path}

    content = path.read_text(encoding="utf-8", errors="replace")
    title = path.stem
    scope = detect_scope(file_path)

    # Find vault
    vault = find_vault(path)
    if not vault:
        return {"status": "no_vault", "path": file_path}

    # Use CLI to push
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "synapse.cli", "push",
                "--title", title,
                "--text", content,
                "--scope", scope,
                "--type", "learning",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(vault.parent),
        )

        if result.returncode == 0:
            return {"status": "indexed", "path": file_path, "scope": scope}
        else:
            return {"status": "error", "path": file_path, "error": result.stderr[:200]}

    except subprocess.TimeoutExpired:
        return {"status": "error", "path": file_path, "error": "push command timed out"}
    except Exception as e:
        return {"status": "error", "path": file_path, "error": str(e)[:200]}


def find_vault(start: Path) -> Path | None:
    """Find .synapse/ vault from start path upward."""
    for p in [start.parent] + list(start.parent.parents):
        vault = p / ".synapse"
        if vault.exists():
            return vault
    return None


if __name__ == "__main__":
    # Called as PostToolUse hook: FILE_PATH is passed as arg
    if len(sys.argv) > 1:
        fp = sys.argv[1]
        if should_process(fp):
            result = process_file(fp)
            # Only output if there's an error (so it shows in hook feedback)
            if result["status"] not in ("indexed", "file_not_found", "no_vault"):
                print(f"[synapse] {result['status']}: {result.get('error', '')}", file=sys.stderr)