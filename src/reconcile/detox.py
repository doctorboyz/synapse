"""Detox — detect and resolve conflicts between documents using LLM."""

import logging

from src.db.pg_store import PgStore
from src.db.qdrant_store import QdrantStore
from src.embed.ollama import OllamaEmbedder
from src.reconcile.llm import analyze_conflict

log = logging.getLogger("synapse.detox")


async def detox(
    pg: PgStore,
    qdrant: QdrantStore | None = None,
    embedder: OllamaEmbedder | None = None,
    settings=None,
    scope: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Detect conflicts between documents and optionally resolve them.

    Returns dict with: conflicts_found, conflicts, resolutions, errors
    """
    # Get all active docs in scope
    all_docs = await pg.list_docs(scope=scope, limit=100, order="newest")

    if not all_docs or len(all_docs) < 2:
        return {
            "conflicts_found": 0,
            "conflicts": [],
            "resolutions": [],
            "errors": 0,
        }

    # Find potential conflicts: docs in same scope with same doc_type
    potential_pairs = []
    seen = set()

    for i, doc_a in enumerate(all_docs):
        for doc_b in all_docs[i + 1:]:
            # Same scope and same doc_type → potential conflict
            if doc_a.get("scope") == doc_b.get("scope") and doc_a.get("doc_type") == doc_b.get("doc_type"):
                pair_key = tuple(sorted([doc_a["id"], doc_b["id"]]))
                if pair_key not in seen:
                    seen.add(pair_key)
                    potential_pairs.append((doc_a, doc_b))

    if not potential_pairs:
        return {
            "conflicts_found": 0,
            "conflicts": [],
            "resolutions": [],
            "errors": 0,
        }

    # Analyze each pair with LLM
    conflicts = []
    resolutions = []
    errors = 0

    for doc_a, doc_b in potential_pairs:
        conflict_info = {
            "doc_a": {"id": str(doc_a["id"]), "title": doc_a.get("title", ""), "scope": doc_a.get("scope", "")},
            "doc_b": {"id": str(doc_b["id"]), "title": doc_b.get("title", ""), "scope": doc_b.get("scope", "")},
            "analysis": None,
            "action": None,
        }

        if embedder and settings:
            # Get full content for analysis
            full_a = await pg.get(doc_a["id"], include_chain=False)
            full_b = await pg.get(doc_b["id"], include_chain=False)

            if not full_a or not full_b:
                log.warning("Missing document for conflict analysis: a=%s b=%s", doc_a.get("id"), doc_b.get("id"))
                errors += 1
                continue

            analysis = await analyze_conflict(
                doc_a={"title": full_a.get("title", ""), "content": (full_a.get("content", "") or "")[:2000]},
                doc_b={"title": full_b.get("title", ""), "content": (full_b.get("content", "") or "")[:2000]},
                settings=settings,
            )
            conflict_info["analysis"] = analysis

            if analysis and analysis.get("is_conflict"):
                conflicts.append(conflict_info)

                if not dry_run and analysis.get("merged_content"):
                    try:
                        supersede_id = analysis.get("supersede_id", "a")
                        old_id = doc_a["id"] if supersede_id == "a" else doc_b["id"]
                        merged_content = analysis["merged_content"]

                        result = await pg.supersede(
                            old_id=str(old_id),
                            new_content=merged_content,
                            reason=f"detox_conflict: {analysis.get('reason', 'conflict detected')}",
                        )
                        conflict_info["action"] = "superseded"
                        conflict_info["new_id"] = result.get("id")
                        resolutions.append({
                            "old_id": str(old_id),
                            "new_id": result.get("id"),
                            "reason": analysis.get("reason"),
                        })
                    except Exception as e:
                        log.error("Failed to resolve conflict: %s", e)
                        errors += 1
                        conflict_info["action"] = "error"
                        conflict_info["error"] = str(e)
            elif analysis:
                # LLM analyzed but no conflict
                pass
            else:
                # LLM unavailable
                conflict_info["analysis"] = {"is_conflict": "unknown", "reason": "LLM unavailable"}
                conflicts.append(conflict_info)
        else:
            # No LLM available
            conflict_info["analysis"] = {"is_conflict": "potential", "reason": "LLM unavailable for analysis"}
            conflicts.append(conflict_info)

    return {
        "conflicts_found": len(conflicts),
        "conflicts": conflicts,
        "resolutions": resolutions,
        "errors": errors,
    }