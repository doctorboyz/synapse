"""Rebuild — recreate vault indexes from source files

Drops and recreates SQLite and LanceDB indexes, preserving config.yaml.
Source files are re-discovered and re-indexed from learnings/ and retrospectives/.
"""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from synapse.exceptions import RebuildError
from synapse.store.sqlite_store import SQLiteStore
from synapse.ingest.push import Push
from synapse.scope.manager import ScopeManager

log = logging.getLogger("synapse.ingest.rebuild")


def discover_source_files(project_path: Path, scope: Optional[str] = None) -> list[Path]:
    """Find all markdown files in learnings/ and retrospectives/ directories.

    Walks the project directory for .md files matching the auto-index trigger
    patterns. If scope is given, only files whose auto-detected scope matches
    are included.
    """
    triggers = ["learnings", "retrospectives"]
    files = []
    seen = set()

    for trigger in triggers:
        # Direct subdirectory: project_path/trigger/
        dir_path = project_path / trigger
        if dir_path.exists() and dir_path.is_dir():
            for md_file in sorted(dir_path.rglob("*.md")):
                if md_file not in seen:
                    files.append(md_file)
                    seen.add(md_file)

    # Also check nested patterns: any directory containing /learnings/ or /retrospectives/
    for md_file in sorted(project_path.rglob("*.md")):
        path_str = str(md_file)
        if any(f"/{t}/" in path_str for t in triggers):
            if md_file not in seen:
                files.append(md_file)
                seen.add(md_file)

    # Filter by scope if specified
    if scope:
        from synapse.scope.manager import detect_scope
        files = [f for f in files if detect_scope(str(f)) == scope]

    return files


def rebuild_vault(
    project_path: Path,
    scope: Optional[str] = None,
    backup: bool = True,
) -> dict:
    """Rebuild vault indexes from source files.

    Steps:
    1. Verify vault exists
    2. Backup vault.db (optional)
    3. Delete vault.db and vectors/ contents
    4. Recreate SQLite schema
    5. Discover source files
    6. Re-index all discovered files
    7. Return stats

    Args:
        project_path: Root directory of the project
        scope: Only rebuild files matching this scope
        backup: Whether to backup vault.db before rebuild

    Returns:
        Dict with status, files_processed, documents_indexed, vectors_indexed, errors

    Raises:
        RebuildError: If vault not found or rebuild fails
    """
    vault = project_path / ".synapse"
    if not vault.exists():
        raise RebuildError(f"No vault found at {vault}. Run 'synapse init' first.")

    db_path = vault / "vault.db"
    vectors_path = vault / "vectors"
    config_path = vault / "config.yaml"

    if not db_path.exists():
        raise RebuildError(f"Vault database not found at {db_path}")

    # Backup vault.db
    if backup:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = vault / f"vault.db.backup.{timestamp}"
        try:
            shutil.copy2(db_path, backup_path)
            log.info("Backed up vault.db to %s", backup_path)
        except OSError as e:
            log.warning("Failed to backup vault.db: %s (continuing anyway)", e)

    # Read existing config before wipe
    config_content = None
    if config_path.exists():
        try:
            config_content = config_path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("Failed to read config.yaml: %s", e)

    # Delete vault.db
    try:
        db_path.unlink()
        log.info("Deleted vault.db for rebuild")
    except OSError as e:
        raise RebuildError(f"Failed to delete vault.db: {e}") from e

    # Delete vectors/ contents
    if vectors_path.exists():
        try:
            shutil.rmtree(vectors_path)
            vectors_path.mkdir(parents=True, exist_ok=True)
            log.info("Cleared vectors/ directory")
        except OSError as e:
            raise RebuildError(f"Failed to clear vectors/ directory: {e}") from e

    # Recreate SQLite schema
    try:
        sqlite = SQLiteStore(vault)
    except Exception as e:
        # Restore backup if available
        if backup and backup_path.exists():
            shutil.copy2(backup_path, db_path)
            log.info("Restored vault.db from backup after rebuild failure")
        raise RebuildError(f"Failed to recreate vault database: {e}") from e

    # Restore config.yaml
    if config_content is not None:
        try:
            config_path.write_text(config_content, encoding="utf-8")
        except OSError as e:
            log.warning("Failed to restore config.yaml: %s", e)

    # Discover source files
    source_files = discover_source_files(project_path, scope)
    log.info("Discovered %d source files to re-index", len(source_files))

    # Try to set up LanceDB for vector re-indexing
    lancedb = None
    try:
        from synapse.store.lancedb_store import LanceDBStore
        lancedb = LanceDBStore(vault)
    except Exception:
        log.warning("LanceDB not available — vectors will not be re-indexed")

    scope_mgr = ScopeManager(sqlite)
    push = Push(sqlite, lancedb, scope_mgr)

    # Re-index all files
    documents_indexed = 0
    vectors_indexed = 0
    errors = []

    for file_path in source_files:
        try:
            result = push.push_file(str(file_path), scope=scope)
            if result.get("status") in ("indexed", "indexed_sqlite_only"):
                documents_indexed += 1
                if lancedb and result.get("status") == "indexed":
                    vectors_indexed += 1
            elif result.get("status") == "file_not_found":
                log.debug("File not found (may have been deleted): %s", file_path)
            else:
                errors.append(f"{file_path}: {result.get('status', 'unknown')}")
        except Exception as e:
            errors.append(f"{file_path}: {e}")
            log.warning("Failed to re-index %s: %s", file_path, e)

    sqlite.close()
    if lancedb:
        lancedb.close()

    stats = {
        "status": "success",
        "vault": str(vault),
        "files_processed": len(source_files),
        "documents_indexed": documents_indexed,
        "vectors_indexed": vectors_indexed if lancedb else 0,
        "errors": errors,
    }

    log.info(
        "Rebuild complete: %d files processed, %d docs indexed, %d vectors",
        len(source_files), documents_indexed, vectors_indexed,
    )

    return stats