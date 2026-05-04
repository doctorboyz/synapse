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
    ConfigError,
    DaemonError,
    DaemonNotRunningError,
    DaemonAlreadyRunningError,
    ProjectRegistrationError,
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


class TestV2Hierarchy:
    def test_config_error_inherits_synapse_error(self):
        assert issubclass(ConfigError, SynapseError)

    def test_daemon_error_inherits_synapse_error(self):
        assert issubclass(DaemonError, SynapseError)

    def test_daemon_not_running_inherits_daemon_error(self):
        assert issubclass(DaemonNotRunningError, DaemonError)

    def test_daemon_already_running_inherits_daemon_error(self):
        assert issubclass(DaemonAlreadyRunningError, DaemonError)

    def test_project_registration_error_inherits_synapse_error(self):
        assert issubclass(ProjectRegistrationError, SynapseError)


class TestV2Catch:
    def test_catch_config_error_as_synapse_error(self):
        with pytest.raises(SynapseError):
            raise ConfigError("bad config")

    def test_catch_daemon_not_running_as_daemon_error(self):
        with pytest.raises(DaemonError):
            raise DaemonNotRunningError("daemon not running")

    def test_catch_daemon_already_running_as_daemon_error(self):
        with pytest.raises(DaemonError):
            raise DaemonAlreadyRunningError("pid lock collision")

    def test_catch_project_registration_as_synapse_error(self):
        with pytest.raises(SynapseError):
            raise ProjectRegistrationError("register failed")