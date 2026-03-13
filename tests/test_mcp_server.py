"""Tests for the MCP server tools (unit tests without running the server)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

# MCP SDK may not be installed; skip gracefully
try:
    from agent_verify.mcp_server import _serialize, get_ast_diff, get_intent, verify_changes
except ImportError:
    pytest.skip("mcp SDK not installed", allow_module_level=True)

from agent_verify.models.diff import ASTChange, ChangeType
from agent_verify.models.intent import Confidence, IntentClaim, IntentType
from agent_verify.models.report import Finding, FindingSeverity, Verdict, VerifyReport

# --- _serialize ---


class TestSerialize:
    def test_pydantic_model(self):
        claim = IntentClaim(
            id="test",
            description="test claim",
            type=IntentType.FEATURE,
            source="test",
            confidence=Confidence.HIGH,
        )
        result = _serialize(claim)
        assert isinstance(result, dict)
        assert result["id"] == "test"
        assert result["type"] == "feature"
        assert result["confidence"] == "high"

    def test_list_of_models(self):
        changes = [
            ASTChange(
                file_path="a.py",
                change_type=ChangeType.ADDED,
                node_type="function",
                name="foo",
            ),
        ]
        result = _serialize(changes)
        assert isinstance(result, list)
        assert result[0]["name"] == "foo"
        assert result[0]["change_type"] == "added"

    def test_nested_dict_with_models(self):
        claim = IntentClaim(
            id="nested",
            description="nested claim",
            type=IntentType.BUGFIX,
            source="test",
            confidence=Confidence.MEDIUM,
        )
        result = _serialize({"key": claim, "list": [claim]})
        assert result["key"]["id"] == "nested"
        assert result["list"][0]["type"] == "bugfix"

    def test_plain_dict(self):
        assert _serialize({"a": 1}) == {"a": 1}

    def test_primitive(self):
        assert _serialize(42) == 42
        assert _serialize("hello") == "hello"
        assert _serialize(None) is None


# --- verify_changes ---


class TestVerifyChanges:
    def test_returns_valid_json(self):
        fake_report = VerifyReport(
            verdict=Verdict.PASS,
            confidence_score=0.85,
            findings=[],
            claims_verified=2,
            claims_total=3,
            claims_unverifiable=1,
            execution_time_seconds=0.5,
            metadata={"diff_ref": "HEAD~1", "files_changed": [], "languages": []},
        )
        with patch("agent_verify.mcp_server.run_pipeline", return_value=fake_report):
            result = verify_changes(diff_ref="HEAD~1", repo_path=".")
            data = json.loads(result)

        assert data["verdict"] == "pass"
        assert data["confidence_score"] == 0.85
        assert data["claims_verified"] == 2
        assert data["claims_total"] == 3
        assert isinstance(data["findings"], list)

    def test_passes_all_params_to_pipeline(self):
        fake_report = VerifyReport(verdict=Verdict.WARN, confidence_score=0.5)
        with patch("agent_verify.mcp_server.run_pipeline", return_value=fake_report) as mock:
            verify_changes(
                diff_ref="abc123",
                pr_body="some body",
                spec_file="SPEC.md",
                repo_path="/tmp/repo",
                use_llm=True,
            )
            mock.assert_called_once_with(
                diff_ref="abc123",
                pr_body="some body",
                spec_file="SPEC.md",
                repo_path="/tmp/repo",
                use_llm=True,
            )

    def test_fail_verdict_with_findings(self):
        fake_report = VerifyReport(
            verdict=Verdict.FAIL,
            confidence_score=0.1,
            findings=[
                Finding(
                    id="f1",
                    severity=FindingSeverity.CRITICAL,
                    category="missing_behavior",
                    title="Missing handler",
                    description="No error handler found",
                    file_path="app.py",
                )
            ],
        )
        with patch("agent_verify.mcp_server.run_pipeline", return_value=fake_report):
            result = verify_changes()
            data = json.loads(result)

        assert data["verdict"] == "fail"
        assert len(data["findings"]) == 1
        assert data["findings"][0]["severity"] == "critical"
        assert data["findings"][0]["category"] == "missing_behavior"

    def test_default_params(self):
        fake_report = VerifyReport(verdict=Verdict.PASS, confidence_score=0.9)
        with patch("agent_verify.mcp_server.run_pipeline", return_value=fake_report) as mock:
            verify_changes()
            mock.assert_called_once_with(
                diff_ref="HEAD~1",
                pr_body="",
                spec_file="",
                repo_path=".",
                use_llm=False,
            )


# --- get_intent ---


class TestGetIntent:
    def test_with_pr_body(self):
        result = get_intent(pr_body="## What\n- Add user authentication endpoint")
        data = json.loads(result)
        assert "claims" in data
        assert len(data["claims"]) >= 1

    def test_with_commits(self):
        result = get_intent(commits="feat: add login,fix: resolve crash")
        data = json.loads(result)
        assert len(data["claims"]) == 2
        types = {c["type"] for c in data["claims"]}
        assert "feature" in types
        assert "bugfix" in types

    def test_with_spec_file(self, tmp_path):
        spec = tmp_path / "SPEC.md"
        spec.write_text("## Requirements\n- Implement JWT token refresh\n- Add rate limiting")
        result = get_intent(spec_file=str(spec))
        data = json.loads(result)
        assert len(data["claims"]) >= 1

    def test_empty_input(self):
        result = get_intent(repo_path="/nonexistent/path")
        data = json.loads(result)
        assert data["claims"] == []

    def test_returns_raw_sources(self):
        result = get_intent(pr_body="## Summary\n- Add caching layer for API responses")
        data = json.loads(result)
        assert "raw_sources" in data

    def test_combined_sources(self):
        result = get_intent(
            pr_body="## What\n- Add login page with OAuth support",
            commits="feat: add OAuth login",
        )
        data = json.loads(result)
        assert len(data["claims"]) >= 2


# --- get_ast_diff ---


class TestGetAstDiff:
    def test_added_function(self):
        old = "def existing():\n    pass\n"
        new = "def existing():\n    pass\n\ndef new_func():\n    return 1\n"
        result = get_ast_diff("test.py", old, new)
        data = json.loads(result)
        assert data["language"] == "python"
        assert len(data["changes"]) >= 1
        added = [c for c in data["changes"] if c["change_type"] == "added"]
        assert len(added) == 1
        assert added[0]["name"] == "new_func"

    def test_removed_function(self):
        old = "def goodbye():\n    pass\n"
        new = ""
        result = get_ast_diff("test.py", old, new)
        data = json.loads(result)
        removed = [c for c in data["changes"] if c["change_type"] == "removed"]
        assert len(removed) == 1
        assert removed[0]["name"] == "goodbye"

    def test_modified_function(self):
        old = "def greet():\n    return 'hi'\n"
        new = "def greet():\n    return 'hello world'\n"
        result = get_ast_diff("test.py", old, new)
        data = json.loads(result)
        modified = [c for c in data["changes"] if c["change_type"] == "modified"]
        assert len(modified) == 1
        assert modified[0]["name"] == "greet"

    def test_unknown_language(self):
        result = get_ast_diff("file.xyz", "a", "b")
        data = json.loads(result)
        assert data["language"] is None
        assert data["changes"] == []

    def test_no_changes(self):
        code = "def same():\n    pass\n"
        result = get_ast_diff("test.py", code, code)
        data = json.loads(result)
        assert data["changes"] == []

    def test_javascript_file(self):
        old = ""
        new = "function fetchData() {\n  return fetch('/api');\n}\n"
        result = get_ast_diff("app.js", old, new)
        data = json.loads(result)
        assert data["language"] == "javascript"
        assert len(data["changes"]) >= 1

    def test_empty_files(self):
        result = get_ast_diff("test.py", "", "")
        data = json.loads(result)
        assert data["changes"] == []


# --- MCP server instance ---


class TestMcpServerEntry:
    def test_mcp_instance_exists(self):
        from agent_verify.mcp_server import mcp

        assert mcp is not None
        assert mcp.name == "agent-verify"

    def test_main_callable(self):
        from agent_verify.mcp_server import main

        assert callable(main)
