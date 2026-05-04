"""Synapse CLI — /synapse push, /synapse search, /synapse status"""

import argparse
import json
import logging
import sys
from pathlib import Path

from synapse.store.sqlite_store import SQLiteStore
from synapse.store.lancedb_store import LanceDBStore
from synapse.retrieve.hybrid_search import HybridSearch
from synapse.scope.manager import ScopeManager, detect_scope
from synapse.ingest.push import Push
from synapse.ingest.init import init_vault
from synapse.exceptions import SynapseError, VaultAlreadyExistsError, LanceDBStoreError
from synapse.logging_config import setup_logging

log = logging.getLogger("synapse.cli")


def find_vault() -> Path:
    """Find or create .synapse/ vault."""
    cwd = Path.cwd()
    for p in [cwd] + list(cwd.parents):
        vault = p / ".synapse"
        if vault.exists():
            return vault
    vault = cwd / ".synapse"
    vault.mkdir(parents=True, exist_ok=True)
    return vault


def cmd_push(args):
    vault = find_vault()
    sqlite = SQLiteStore(vault)
    try:
        lancedb = LanceDBStore(vault)
    except (ImportError, LanceDBStoreError):
        lancedb = None
    scope_mgr = ScopeManager(sqlite)
    pusher = Push(sqlite, lancedb, scope_mgr)

    if args.file:
        result = pusher.push_file(args.file, scope=args.scope, doc_type=args.type)
    elif args.text:
        result = pusher.push_text(
            title=args.title or "untitled",
            content=args.text,
            scope=args.scope,
            doc_type=args.type,
        )
    else:
        # Read from stdin
        content = sys.stdin.read()
        result = pusher.push_text(
            title=args.title or "untitled",
            content=content,
            scope=args.scope,
            doc_type=args.type,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    sqlite.close()
    if lancedb:
        lancedb.close()


def cmd_search(args):
    vault = find_vault()
    sqlite = SQLiteStore(vault)
    try:
        lancedb = LanceDBStore(vault)
        search = HybridSearch(sqlite, lancedb)
    except (ImportError, LanceDBStoreError):
        lancedb = None
        search = None

    if search:
        results = search.search(
            query=args.query,
            scope=args.scope,
            limit=args.limit,
            mode=args.mode,
        )
    else:
        results = sqlite.search_fts5(args.query, scope=args.scope, limit=args.limit)

    if results:
        for r in results:
            score = r.get("score", 0)
            title = r.get("title", "?")
            scope = r.get("scope", "?")
            doc_type = r.get("doc_type", "?")
            doc_id = r.get("id", "?")
            print(f"  [{scope}] {title} ({doc_type}) score={score:.4f} id={doc_id[:8]}")
    else:
        print("No results found.")

    sqlite.close()
    if lancedb:
        lancedb.close()


def cmd_status(args):
    vault = find_vault()
    sqlite = SQLiteStore(vault)

    stats = sqlite.stats()
    print(f"Synapse Vault: {vault}")
    print(f"  Documents: {stats['total_documents']}")
    print(f"  Superseded: {stats['superseded_documents']}")
    print(f"  Scopes:")
    for scope, count in stats["by_scope"].items():
        print(f"    {scope}: {count} docs")
    print(f"  Types:")
    for dtype, count in stats["by_type"].items():
        print(f"    {dtype}: {count} docs")

    lancedb = None
    try:
        lancedb = LanceDBStore(vault)
        vec_stats = lancedb.stats()
        print(f"  Vectors: {vec_stats['total_vectors']} ({vec_stats['embedding_dim']}-dim)")
    except (ImportError, LanceDBStoreError):
        print(f"  Vectors: lancedb not installed")
    finally:
        if lancedb:
            lancedb.close()

    sqlite.close()


def cmd_scope(args):
    vault = find_vault()
    sqlite = SQLiteStore(vault)
    scope_mgr = ScopeManager(sqlite)

    scopes = scope_mgr.list_scopes()
    if scopes:
        for s in scopes:
            print(f"  {s['name']}: {s['doc_count']} docs")
    else:
        print("No scopes yet.")

    sqlite.close()


def cmd_init(args):
    project = Path.cwd()
    try:
        result = init_vault(project, scope=args.scope)
    except VaultAlreadyExistsError as e:
        print(f"Vault already exists: {e}")
        return

    print(f"Initialized synapse vault:")
    print(f"  Vault:     {result['vault']}")
    print(f"  Database:  {result['vault_db']}")
    print(f"  Vectors:   {result['vectors']}")
    print(f"  Config:    {result['config']}")
    print(f"  Gitignore: {result['gitignore']}")


def cmd_rebuild(args):
    from synapse.ingest.rebuild import rebuild_vault
    project = Path.cwd()
    result = rebuild_vault(project, scope=args.scope, backup=not args.no_backup)
    if result["status"] == "success":
        print(f"Rebuilt vault:")
        print(f"  Files processed: {result['files_processed']}")
        print(f"  Documents indexed: {result['documents_indexed']}")
        print(f"  Vectors indexed: {result['vectors_indexed']}")
        if result["errors"]:
            print(f"  Errors: {len(result['errors'])}")
            for err in result["errors"][:5]:
                print(f"    {err}")
    else:
        print(f"Rebuild failed: {result.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="synapse", description="Synapse — Hybrid Knowledge Framework")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose (INFO) logging")

    sub = parser.add_subparsers(dest="command")

    # push
    p_push = sub.add_parser("push", help="Add knowledge to vault")
    p_push.add_argument("file", nargs="?", help="File to push")
    p_push.add_argument("--title", help="Document title")
    p_push.add_argument("--text", help="Text content")
    p_push.add_argument("--scope", help="Scope (shared / project-name)")
    p_push.add_argument("--type", default="learning", help="Doc type (learning/pattern/architecture)")
    p_push.set_defaults(func=cmd_push)

    # search
    p_search = sub.add_parser("search", help="Search knowledge vault")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--scope", help="Filter to scope")
    p_search.add_argument("--limit", type=int, default=10, help="Max results")
    p_search.add_argument("--mode", default="hybrid", choices=["hybrid", "dense", "fts"], help="Search mode")
    p_search.set_defaults(func=cmd_search)

    # status
    p_status = sub.add_parser("status", help="Vault statistics")
    p_status.set_defaults(func=cmd_status)

    # scope
    p_scope = sub.add_parser("scope", help="List scopes")
    p_scope.set_defaults(func=cmd_scope)

    # init
    p_init = sub.add_parser("init", help="Initialize .synapse/ vault in current project")
    p_init.add_argument("--scope", help="Default scope for this project")
    p_init.set_defaults(func=cmd_init)

    # rebuild
    p_rebuild = sub.add_parser("rebuild", help="Rebuild vault indexes from source files")
    p_rebuild.add_argument("--scope", help="Only rebuild a specific scope")
    p_rebuild.add_argument("--no-backup", action="store_true", help="Skip vault.db backup before rebuild")
    p_rebuild.set_defaults(func=cmd_rebuild)

    args = parser.parse_args()

    if args.verbose:
        setup_logging("INFO")

    if hasattr(args, "func"):
        try:
            args.func(args)
        except SynapseError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(130)
        except Exception as e:
            log.exception("Unexpected error")
            print(f"Unexpected error: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()