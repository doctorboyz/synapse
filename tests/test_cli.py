"""Tests for CLI commands — parser structure and command dispatch."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.main import build_parser, COMMAND_DISPATCH


class TestCLIParser:
    def test_parser_has_all_commands(self):
        parser = build_parser()
        # Each command needs appropriate args to parse successfully
        test_args = {
            "serve": [],
            "mcp": [],
            "push": ["--title", "t", "--content", "c"],
            "search": ["test query"],
            "get": ["some-id"],
            "list": [],
            "scope": [],
            "stats": [],
            "supersede": ["old-id", "--new-content", "new"],
            "trace": ["--source", "a", "--target", "b", "--relation", "derived_from"],
            "trace-chain": ["some-id"],
            "concepts": [],
            "init": [],
            "reconcile": [],
        }
        for cmd, args in test_args.items():
            parsed = parser.parse_args([cmd] + args)
            assert parsed.command == cmd, f"Command {cmd} not recognized"

    def test_push_text_mode(self):
        parser = build_parser()
        args = parser.parse_args(["push", "--title", "Test", "--content", "Hello", "--scope", "test"])
        assert args.command == "push"
        assert args.title == "Test"
        assert args.content == "Hello"
        assert args.scope == "test"

    def test_push_file_mode(self):
        parser = build_parser()
        args = parser.parse_args(["push", "--file", "/path/to/doc.md", "--scope", "my-project"])
        assert args.command == "push"
        assert args.file == "/path/to/doc.md"
        assert args.scope == "my-project"

    def test_push_with_concepts_tags(self):
        parser = build_parser()
        args = parser.parse_args([
            "push", "--title", "Test", "--content", "Hello",
            "--concepts", "python,async", "--tags", "code,example"
        ])
        assert args.concepts == "python,async"
        assert args.tags == "code,example"

    def test_search_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["search", "async patterns"])
        assert args.command == "search"
        assert args.query == "async patterns"
        assert args.limit == 10
        assert args.mode == "hybrid"

    def test_search_with_filters(self):
        parser = build_parser()
        args = parser.parse_args([
            "search", "test query", "--scope", "my-project",
            "--doc-type", "learning", "--limit", "5", "--mode", "fts"
        ])
        assert args.scope == "my-project"
        assert args.doc_type == "learning"
        assert args.limit == 5
        assert args.mode == "fts"

    def test_get_command(self):
        parser = build_parser()
        args = parser.parse_args(["get", "abc-123"])
        assert args.command == "get"
        assert args.id == "abc-123"
        assert args.no_chain is False

    def test_get_no_chain(self):
        parser = build_parser()
        args = parser.parse_args(["get", "abc-123", "--no-chain"])
        assert args.no_chain is True

    def test_list_command(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--scope", "test", "--limit", "10"])
        assert args.command == "list"
        assert args.scope == "test"
        assert args.limit == 10

    def test_supersede_command(self):
        parser = build_parser()
        args = parser.parse_args(["supersede", "old-id", "--new-content", "updated content"])
        assert args.command == "supersede"
        assert args.old_id == "old-id"
        assert args.new_content == "updated content"
        assert args.reason == "updated"

    def test_trace_command(self):
        parser = build_parser()
        args = parser.parse_args([
            "trace", "--source", "id-1", "--target", "id-2",
            "--relation", "derived_from", "--confidence", "0.9"
        ])
        assert args.command == "trace"
        assert args.source == "id-1"
        assert args.target == "id-2"
        assert args.relation == "derived_from"
        assert args.confidence == 0.9

    def test_trace_chain_command(self):
        parser = build_parser()
        args = parser.parse_args(["trace-chain", "doc-id", "--direction", "upstream", "--max-depth", "3"])
        assert args.command == "trace-chain"
        assert args.doc_id == "doc-id"
        assert args.direction == "upstream"
        assert args.max_depth == 3

    def test_init_command(self):
        parser = build_parser()
        args = parser.parse_args(["init", "--path", "/my/project", "--scope", "test", "--dry-run"])
        assert args.command == "init"
        assert args.path == "/my/project"
        assert args.scope == "test"
        assert args.dry_run is True

    def test_init_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["init"])
        assert args.path == "."
        assert args.scope is None
        assert args.dry_run is False

    def test_reconcile_command(self):
        parser = build_parser()
        args = parser.parse_args(["reconcile", "--scope", "my-project", "--dry-run"])
        assert args.command == "reconcile"
        assert args.scope == "my-project"
        assert args.dry_run is True


class TestCommandDispatch:
    def test_all_commands_have_handlers(self):
        # serve and mcp are handled separately
        for cmd in ["push", "search", "get", "list", "scope", "stats",
                    "supersede", "trace", "trace-chain", "concepts", "init", "reconcile"]:
            assert cmd in COMMAND_DISPATCH, f"Missing dispatch for {cmd}"
            assert COMMAND_DISPATCH[cmd] is not None, f"No handler for {cmd}"

    def test_serve_mcp_no_dispatch(self):
        assert COMMAND_DISPATCH.get("serve") is None
        assert COMMAND_DISPATCH.get("mcp") is None


class TestParseHelpers:
    def test_parse_list_comma_separated(self):
        from src.main import _parse_list
        assert _parse_list("python,async,web") == ["python", "async", "web"]
        assert _parse_list("single") == ["single"]
        assert _parse_list("a, b, c") == ["a", "b", "c"]
        assert _parse_list(None) is None
        assert _parse_list("") == []

    def test_json_dump(self):
        from src.main import json_dump
        result = json_dump({"key": "value"})
        import json
        parsed = json.loads(result)
        assert parsed["key"] == "value"