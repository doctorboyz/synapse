"""Reconcile — defrag duplicates + detox conflicts."""

from src.reconcile.defrag import defrag
from src.reconcile.detox import detox


async def reconcile(
    pg,
    qdrant=None,
    embedder=None,
    settings=None,
    scope: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run full reconcile: defrag + detox.

    Returns combined results from both operations.
    """
    defrag_result = await defrag(pg, scope=scope, dry_run=dry_run)
    detox_result = await detox(
        pg, qdrant=qdrant, embedder=embedder, settings=settings,
        scope=scope, dry_run=dry_run,
    )

    return {
        "defrag": defrag_result,
        "detox": detox_result,
        "scope": scope or "all",
        "dry_run": dry_run,
    }