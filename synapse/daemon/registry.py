"""Project Registry — register/unregister projects with shared vault.

Maps project paths to scope prefixes so the daemon can serve multiple
projects from a single ~/.synapse/ vault.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from synapse.exceptions import ProjectRegistrationError

log = logging.getLogger("synapse.daemon.registry")


class ProjectRegistry:
    """Manage project registrations in projects.yaml.

    Each project has:
        - path: absolute path to project root
        - scope: scope prefix used in the shared vault
        - registered_at: ISO timestamp
    """

    def __init__(self, vault_path: Path):
        self._vault_path = vault_path
        self._projects_file = vault_path / "projects.yaml"
        self._projects: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """Load projects.yaml from disk."""
        if self._projects_file.exists():
            try:
                raw = yaml.safe_load(self._projects_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._projects = raw
                else:
                    self._projects = {}
            except yaml.YAMLError as e:
                log.warning("Failed to parse projects.yaml: %s", e)
                self._projects = {}
        else:
            self._projects = {}

    def _save(self) -> None:
        """Persist projects.yaml to disk."""
        self._vault_path.mkdir(parents=True, exist_ok=True)
        self._projects_file.write_text(
            yaml.dump(self._projects, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def register(self, project_path: str, scope: Optional[str] = None) -> dict:
        """Register a project with the shared vault.

        Args:
            project_path: Absolute path to project root.
            scope: Scope prefix (auto-detected from path if omitted).

        Returns:
            Registration dict with path, scope, registered_at.
        """
        abs_path = os.path.abspath(os.path.expanduser(project_path))

        if not Path(abs_path).exists():
            raise ProjectRegistrationError(f"Project path does not exist: {abs_path}")

        # Auto-detect scope from path if not provided
        if not scope:
            scope = self._scope_from_path(abs_path)

        # Check for duplicate registration
        for key, proj in self._projects.items():
            if proj["path"] == abs_path:
                raise ProjectRegistrationError(f"Project already registered as scope '{key}': {abs_path}")

        # Check for scope collision
        if scope in self._projects:
            raise ProjectRegistrationError(
                f"Scope '{scope}' already registered for {self._projects[scope]['path']}"
            )

        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "path": abs_path,
            "scope": scope,
            "registered_at": now,
        }
        self._projects[scope] = entry
        self._save()

        log.info("Registered project: %s → scope '%s'", abs_path, scope)
        return entry

    def unregister(self, scope: str) -> dict:
        """Remove a project registration by scope.

        Returns the removed entry.
        """
        if scope not in self._projects:
            raise ProjectRegistrationError(f"Scope '{scope}' is not registered")

        entry = self._projects.pop(scope)
        self._save()

        log.info("Unregistered scope '%s' (was: %s)", scope, entry["path"])
        return entry

    def list_projects(self) -> list[dict]:
        """List all registered projects."""
        return [
            {"scope": scope, **info}
            for scope, info in sorted(self._projects.items())
        ]

    def get_scope(self, project_path: str) -> Optional[str]:
        """Find the scope for a given project path."""
        abs_path = os.path.abspath(os.path.expanduser(project_path))
        for scope, info in self._projects.items():
            if info["path"] == abs_path:
                return scope
        return None

    def get_all_scopes(self) -> list[str]:
        """Get all registered scope names."""
        return list(self._projects.keys())

    def _scope_from_path(self, path: str) -> str:
        """Derive a scope name from a project path."""
        p = Path(path)
        # Use the last directory component as scope
        name = p.name.lower().replace("_", "-").replace(" ", "-")
        # Sanitize: keep only alphanumeric and dashes
        import re
        name = re.sub(r"[^a-z0-9-]", "", name)
        if not name or not name[0].isalpha():
            name = f"proj-{name}"
        return name