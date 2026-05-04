"""Tests for synapse.exceptions — hierarchy and base catch."""

import pytest

from synapse.exceptions import (
    SynapseError,
    VaultError,
    VaultAlreadyExistsError,
    StoreError,
    SQLiteStoreError,
    LanceDBStoreError,
    EmbeddingError,
    ScopeError,
    SearchError,
    RebuildError,
)


class TestHierarchy:
    def test_all_inherit_from_synapse_error(self):
        for exc_cls in [VaultError, StoreError, EmbeddingError, ScopeError, SearchError, RebuildError]:
            assert issubclass(exc_cls, SynapseError)

    def test_vault_already_exists_inherits_vault_error(self):
        assert issubclass(VaultAlreadyExistsError, VaultError)

    def test_sqlite_store_error_inherits_store_error(self):
        assert issubclass(SQLiteStoreError, StoreError)

    def test_lancedb_store_error_inherits_store_error(self):
        assert issubclass(LanceDBStoreError, StoreError)


class TestBaseCatch:
    def test_catch_vault_error_as_synapse_error(self):
        with pytest.raises(SynapseError):
            raise VaultError("vault not found")

    def test_catch_store_error_as_synapse_error(self):
        with pytest.raises(SynapseError):
            raise SQLiteStoreError("db broken")

    def test_catch_specific_vault_already_exists(self):
        with pytest.raises(VaultAlreadyExistsError):
            raise VaultAlreadyExistsError(".synapse exists")

    def test_catch_vault_already_exists_as_vault_error(self):
        with pytest.raises(VaultError):
            raise VaultAlreadyExistsError(".synapse exists")

    def test_catch_embedding_error(self):
        with pytest.raises(SynapseError):
            raise EmbeddingError("ollama down")

    def test_error_message_preserved(self):
        err = ScopeError("invalid scope: BAD")
        assert str(err) == "invalid scope: BAD"