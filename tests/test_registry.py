"""Tests for synapse.daemon.registry — ProjectRegistry."""

import pytest
from pathlib import Path

from synapse.daemon.registry import ProjectRegistry
from synapse.exceptions import ProjectRegistrationError


@pytest.fixture
def vault_path(tmp_path):
    """Create a temporary vault directory."""
    vault = tmp_path / ".synapse"
    vault.mkdir()
    return vault


@pytest.fixture
def registry(vault_path):
    """Create a ProjectRegistry backed by a temp vault."""
    return ProjectRegistry(vault_path)


class TestRegister:
    def test_register_project(self, registry, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        result = registry.register(str(project))
        assert result["scope"] == "my-project"
        assert result["path"] == str(project)
        assert "registered_at" in result

    def test_register_with_explicit_scope(self, registry, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        result = registry.register(str(project), scope="custom-scope")
        assert result["scope"] == "custom-scope"

    def test_register_nonexistent_path_raises(self, registry):
        with pytest.raises(ProjectRegistrationError, match="does not exist"):
            registry.register("/nonexistent/path")

    def test_register_duplicate_path_raises(self, registry, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        registry.register(str(project))
        with pytest.raises(ProjectRegistrationError, match="already registered"):
            registry.register(str(project))

    def test_register_duplicate_scope_raises(self, registry, tmp_path):
        project1 = tmp_path / "project-a"
        project1.mkdir()
        project2 = tmp_path / "project-b"
        project2.mkdir()
        registry.register(str(project1), scope="same-scope")
        with pytest.raises(ProjectRegistrationError, match="already registered"):
            registry.register(str(project2), scope="same-scope")

    def test_register_persists_to_yaml(self, registry, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        registry.register(str(project))

        # Create a new registry instance to verify persistence
        registry2 = ProjectRegistry(registry._vault_path)
        projects = registry2.list_projects()
        assert len(projects) == 1
        assert projects[0]["scope"] == "my-project"


class TestUnregister:
    def test_unregister_project(self, registry, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        registry.register(str(project))
        result = registry.unregister("my-project")
        assert result["scope"] == "my-project"
        assert len(registry.list_projects()) == 0

    def test_unregister_nonexistent_raises(self, registry):
        with pytest.raises(ProjectRegistrationError, match="not registered"):
            registry.unregister("nonexistent")


class TestListProjects:
    def test_list_empty(self, registry):
        assert registry.list_projects() == []

    def test_list_multiple(self, registry, tmp_path):
        for name in ["alpha", "beta", "gamma"]:
            p = tmp_path / name
            p.mkdir()
            registry.register(str(p))

        projects = registry.list_projects()
        assert len(projects) == 3
        scopes = [p["scope"] for p in projects]
        assert "alpha" in scopes
        assert "beta" in scopes
        assert "gamma" in scopes


class TestGetScope:
    def test_get_scope_for_registered_project(self, registry, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        registry.register(str(project))
        scope = registry.get_scope(str(project))
        assert scope == "my-project"

    def test_get_scope_for_unregistered_project(self, registry):
        scope = registry.get_scope("/some/unregistered/path")
        assert scope is None


class TestGetAllScopes:
    def test_get_all_scopes(self, registry, tmp_path):
        for name in ["alpha", "beta"]:
            p = tmp_path / name
            p.mkdir()
            registry.register(str(p))
        scopes = registry.get_all_scopes()
        assert set(scopes) == {"alpha", "beta"}


class TestScopeFromPath:
    def test_scope_from_simple_path(self, registry):
        assert registry._scope_from_path("/home/user/my-project") == "my-project"

    def test_scope_from_path_with_underscores(self, registry):
        result = registry._scope_from_path("/home/user/my_project")
        assert result == "my-project"

    def test_scope_from_path_with_spaces(self, registry):
        result = registry._scope_from_path("/home/user/my project")
        assert result == "my-project"

    def test_scope_from_path_numeric_start(self, registry):
        result = registry._scope_from_path("/home/user/123project")
        assert result.startswith("proj-")