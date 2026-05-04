"""Init — create .synapse/ vault in a project

Creates vault.db, vectors/, config.yaml, updates .gitignore
"""

import logging
import shutil
import sqlite3
from pathlib import Path

import yaml

from synapse.exceptions import VaultError, VaultAlreadyExistsError

log = logging.getLogger("synapse.ingest.init")


DEFAULT_CONFIG = {
    "version": 1,
    "embedding": {
        "model": "nomic-embed-text",
        "dim": 768,
    },
    "search": {
        "mode": "hybrid",
        "weights": {"dense": 0.6, "fts": 0.4},
    },
    "scope": {
        "default": "shared",
    },
    "retrieval": {
        "priority": "stage2",
        "after": ["CLAUDE.md", ".claude/docs", "psi vault"],
    },
}


def init_vault(project_path: Path, scope: str | None = None) -> dict:
    """Initialize .synapse/ vault in a project.

    Returns dict with created paths and status.
    """
    vault = project_path / ".synapse"

    if vault.exists():
        raise VaultAlreadyExistsError(str(vault))

    try:
        # 1. Create .synapse/ directory
        vault.mkdir(parents=True, exist_ok=True)

        # 2. Init SQLite (just connecting creates the schema)
        from synapse.store.sqlite_store import SQLiteStore
        sqlite = SQLiteStore(vault)
        sqlite.close()

        # 3. Create vectors/ for LanceDB
        vectors = vault / "vectors"
        vectors.mkdir(parents=True, exist_ok=True)

        # 4. Create config.yaml
        config = dict(DEFAULT_CONFIG)
        if scope:
            config["scope"]["default"] = scope

        config_path = vault / "config.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False), encoding="utf-8")

        # 5. Add .synapse/ to .gitignore
        gitignore = project_path / ".gitignore"
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
            "gitignore": str(gitignore),
        }
    except (OSError, sqlite3.Error) as e:
        log.error("Vault creation failed, cleaning up: %s", e)
        shutil.rmtree(vault, ignore_errors=True)
        raise VaultError(f"Failed to create vault: {e}") from e