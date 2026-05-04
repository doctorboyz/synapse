"""Init — create .synapse/ vault in a project

Creates vault.db, vectors/, config.yaml, updates .gitignore
"""

import logging
import shutil
import sqlite3
from pathlib import Path

import yaml

from synapse.config import DEFAULT_V1_CONFIG, DEFAULT_V2_CONFIG
from synapse.exceptions import VaultError, VaultAlreadyExistsError

log = logging.getLogger("synapse.ingest.init")


def init_vault(project_path: Path, scope: str | None = None, shared: bool = False) -> dict:
    """Initialize .synapse/ vault in a project.

    Args:
        project_path: Root path of the project (or home dir for shared vault).
        scope: Default scope for documents.
        shared: If True, create shared vault at ~/.synapse/ with v2 config.

    Returns dict with created paths and status.
    """
    if shared:
        vault = project_path / ".synapse"
    else:
        vault = project_path / ".synapse"

    if vault.exists():
        raise VaultAlreadyExistsError(str(vault))

    try:
        # 1. Create .synapse/ directory
        vault.mkdir(parents=True, exist_ok=True)

        # 2. Init SQLite with appropriate WAL mode
        from synapse.store.sqlite_store import SQLiteStore
        wal_mode = shared  # Shared vaults need WAL for concurrent access
        sqlite = SQLiteStore(vault, wal_mode=wal_mode)
        sqlite.close()

        # 3. Create vectors/ for LanceDB
        vectors = vault / "vectors"
        vectors.mkdir(parents=True, exist_ok=True)

        # 4. Create config.yaml (v2 for shared, v1 for per-project)
        if shared:
            config = dict(DEFAULT_V2_CONFIG)
            if scope:
                config["scope"]["default"] = scope
        else:
            config = dict(DEFAULT_V1_CONFIG)
            if scope:
                config["scope"]["default"] = scope

        config_path = vault / "config.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False), encoding="utf-8")

        # 5. Add .synapse/ to .gitignore (per-project only)
        gitignore = project_path / ".gitignore"
        if not shared:
            gitignore_entry = "\n# Synapse vault (local knowledge DB, not committed)\n.synapse/\n"

            if gitignore.exists():
                content = gitignore.read_text(encoding="utf-8", errors="replace")
                if ".synapse/" not in content:
                    gitignore.write_text(content.rstrip() + "\n" + gitignore_entry, encoding="utf-8")
            else:
                gitignore.write_text(gitignore_entry.lstrip(), encoding="utf-8")

        return {
            "status": "initialized",
            "vault": str(vault),
            "vault_db": str(vault / "vault.db"),
            "vectors": str(vectors),
            "config": str(config_path),
            "gitignore": str(gitignore) if not shared else None,
            "shared": shared,
            "version": 2 if shared else 1,
        }
    except (OSError, sqlite3.Error) as e:
        log.error("Vault creation failed, cleaning up: %s", e)
        shutil.rmtree(vault, ignore_errors=True)
        raise VaultError(f"Failed to create vault: {e}") from e