"""Scope manager — shared / project scoping

Inspired by: MemPalace (wing/room), arra-oracle (project field)
"""

import logging
import re
from pathlib import Path
from typing import Optional

from synapse.exceptions import ScopeError

log = logging.getLogger("synapse.scope.manager")

# Known project patterns in file paths
PROJECT_PATTERNS = [
    re.compile(r"/github\.com/[^/]+/([^/]+)/"),
    re.compile(r"/Code/([^/]+)/"),
]


def detect_scope(file_path: str) -> str:
    """Auto-detect scope from file path.

    Returns project name if found, otherwise 'shared'.
    """
    for pattern in PROJECT_PATTERNS:
        match = pattern.search(file_path)
        if match:
            return match.group(1)

    if "memory/learnings/" in file_path or "learnings/" in file_path:
        parent = Path(file_path).parent
        for part in parent.parts:
            for pat in PROJECT_PATTERNS:
                m = pat.search(f"/{part}/")
                if m:
                    return m.group(1)

    return "shared"


def validate_scope(scope: str) -> bool:
    """Validate scope name: lowercase, alphanumeric, dashes only."""
    return bool(re.match(r"^[a-z][a-z0-9-]{0,49}$", scope))


class ScopeManager:
    """Manage knowledge scopes."""

    def __init__(self, sqlite_store):
        self.sqlite = sqlite_store

    def list_scopes(self) -> list[dict]:
        return self.sqlite.list_scopes()

    def resolve_scope(self, file_path: Optional[str], explicit_scope: Optional[str] = None) -> str:
        """Resolve scope: explicit > auto-detect > shared."""
        if explicit_scope:
            if not validate_scope(explicit_scope):
                raise ScopeError(f"Invalid scope name: {explicit_scope}")
            return explicit_scope

        if file_path:
            return detect_scope(file_path)

        return "shared"

    def scope_summary(self, scope: str) -> dict:
        """Get summary stats for a scope."""
        stats = self.sqlite.stats()
        scope_count = stats["by_scope"].get(scope, 0)
        return {
            "scope": scope,
            "document_count": scope_count,
        }