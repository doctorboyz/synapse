"""Synapse exception hierarchy.

All Synapse-specific errors inherit from SynapseError so callers can
catch the base class for generic handling or specific subclasses for
targeted recovery.
"""


class SynapseError(Exception):
    """Base exception for all Synapse errors."""
    pass


class VaultError(SynapseError):
    """Vault I/O, initialization, or structure errors."""
    pass


class VaultAlreadyExistsError(VaultError):
    """Raised when init is called on an existing vault without overwrite."""
    pass


class StoreError(SynapseError):
    """Storage operation failures (SQLite or LanceDB)."""
    pass


class SQLiteStoreError(StoreError):
    """SQLite-specific operation failure."""
    pass


class LanceDBStoreError(StoreError):
    """LanceDB-specific operation failure."""
    pass


class EmbeddingError(SynapseError):
    """Ollama embedding call failures (down, timeout, bad response)."""
    pass


class ScopeError(SynapseError):
    """Invalid or unresolvable scope."""
    pass


class SearchError(SynapseError):
    """Search operation failure (FTS5 parse, hybrid merge)."""
    pass


class RebuildError(SynapseError):
    """Rebuild operation failure (backup, schema drop, re-index)."""
    pass