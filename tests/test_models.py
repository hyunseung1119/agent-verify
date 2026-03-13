"""Tests for data models."""

from __future__ import annotations

from agent_verify.models.diff import ASTChange, ChangeType, DiffGraph
from agent_verify.models.intent import Confidence, IntentClaim, IntentGraph, IntentType
from agent_verify.models.report import (
    Finding,
    FindingSeverity,
    MutationResult,
    Verdict,
    VerifyReport,
)


class TestIntentGraph:
    def test_claim_count(self):
        graph = IntentGraph(claims=[
            IntentClaim(
                id="1", description="test", type=IntentType.FEATURE,
                source="test", confidence=Confidence.HIGH,
            ),
        ])
        assert graph.claim_count == 1

    def test_empty_claim_count(self):
        assert IntentGraph().claim_count == 0

    def test_high_confidence_claims(self):
        claims = [
            IntentClaim(id="1", description="high", type=IntentType.FEATURE,
                        source="test", confidence=Confidence.HIGH),
            IntentClaim(id="2", description="low", type=IntentType.FEATURE,
                        source="test", confidence=Confidence.LOW),
        ]
        graph = IntentGraph(claims=claims)
        assert len(graph.high_confidence_claims) == 1
        assert graph.high_confidence_claims[0].id == "1"


class TestDiffGraph:
    def test_change_count(self):
        graph = DiffGraph(ast_changes=[
            ASTChange(file_path="a.py", change_type=ChangeType.ADDED,
                      node_type="function", name="f"),
        ])
        assert graph.change_count == 1

    def test_changes_for_file(self):
        changes = [
            ASTChange(file_path="a.py", change_type=ChangeType.ADDED,
                      node_type="function", name="f1"),
            ASTChange(file_path="b.py", change_type=ChangeType.ADDED,
                      node_type="function", name="f2"),
        ]
        graph = DiffGraph(ast_changes=changes)
        assert len(graph.changes_for_file("a.py")) == 1
        assert len(graph.changes_for_file("c.py")) == 0


class TestMutationResult:
    def test_kill_rate(self):
        result = MutationResult(total_mutants=10, killed=7, survived=3)
        assert result.kill_rate == 0.7

    def test_kill_rate_zero_mutants(self):
        result = MutationResult()
        assert result.kill_rate == 0.0


class TestVerifyReport:
    def test_critical_findings(self):
        findings = [
            Finding(id="1", severity=FindingSeverity.CRITICAL,
                    category="test", title="bad", description="bad"),
            Finding(id="2", severity=FindingSeverity.LOW,
                    category="test", title="ok", description="ok"),
        ]
        report = VerifyReport(verdict=Verdict.FAIL, findings=findings)
        assert len(report.critical_findings) == 1

    def test_has_failures(self):
        report = VerifyReport(verdict=Verdict.FAIL)
        assert report.has_failures is True

        report = VerifyReport(verdict=Verdict.PASS)
        assert report.has_failures is False

    def test_to_summary(self):
        report = VerifyReport(
            verdict=Verdict.PASS,
            confidence_score=0.85,
            claims_verified=3,
            claims_total=4,
        )
        summary = report.to_summary()
        assert "PASS" in summary
        assert "3/4" in summary
