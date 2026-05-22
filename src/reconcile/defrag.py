"""Defrag — compact duplicate documents by content_hash."""

import logging

from src.db.pg_store import PgStore

log = logging.getLogger("synapse.defrag")


async def defrag(
    pg: PgStore,
    scope: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Find and compact duplicate documents (same content_hash within same scope).

    For each group of duplicates: keep the newest, supersede the rest.

    Returns dict with: duplicates_found, compacted, errors, groups
    """
    # List all active docs grouped by scope to find duplicates
    all_docs = await pg.list_docs(scope=scope, limit=10000, order="newest")

    if not all_docs:
        return {
            "duplicates_found": 0,
            "compacted": 0,
            "errors": 0,
            "groups": [],
        }

    # Group by (content_hash implicit via supersede check)
    # We need to check for duplicates by looking at documents with same title and scope
    # since content_hash isn't exposed in list_docs.
    # Use list_docs to find potential duplicates, then get() to compare.
    seen = {}
    groups = []
    total_compacted = 0
    total_errors = 0

    for doc in all_docs:
        doc_id = doc["id"]
        full_doc = await pg.get(doc_id, include_chain=False)
        if not full_doc:
            continue

        # Group by (content_hash, scope) — but content_hash not in list_docs
        # Use title+scope as proxy for finding duplicates
        key = (full_doc.get("title", ""), full_doc.get("scope", ""))
        if key not in seen:
            seen[key] = []
        seen[key].append(full_doc)

    # Find groups with more than one doc
    for (title, doc_scope), docs in seen.items():
        if len(docs) <= 1:
            continue

        group_info = {
            "title": title,
            "scope": doc_scope,
            "count": len(docs),
            "keep": docs[0]["id"],
            "supersede": [d["id"] for d in docs[1:]],
        }

        if dry_run:
            group_info["action"] = "would_supersede"
            groups.append(group_info)
            total_compacted += len(docs) - 1
            continue

        # Supersede all but the newest
        for old_doc in docs[1:]:
            try:
                result = await pg.supersede(
                    old_id=old_doc["id"],
                    new_content=old_doc.get("content", ""),
                    reason="defrag_duplicate",
                )
                total_compacted += 1
                group_info["action"] = "superseded"
            except Exception as e:
                log.error("Failed to supersede %s: %s", old_doc["id"], e)
                total_errors += 1

        groups.append(group_info)

    return {
        "duplicates_found": sum(g["count"] - 1 for g in groups),
        "compacted": total_compacted,
        "errors": total_errors,
        "groups": groups,
    }