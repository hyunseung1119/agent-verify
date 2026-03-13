"""Tests for alignment verification."""

from __future__ import annotations

from agent_verify.models.diff import ASTChange, ChangeType, DiffGraph
from agent_verify.models.intent import Confidence, IntentClaim, IntentGraph, IntentType
from agent_verify.models.report import FindingSeverity
from agent_verify.verifiers.alignment import verify_alignment


def _make_intent(descriptions: list[str], confidence: Confidence = Confidence.MEDIUM) -> IntentGraph:
    claims = [
        IntentClaim(
            id=f"test-{i:03d}",
            description=desc,
            type=IntentType.FEATURE,
            source="test",
            confidence=confidence,
        )
        for i, desc in enumerate(descriptions)
    ]
    return IntentGraph(claims=claims)


def _make_diff(names: list[str], files: list[str] | None = None) -> DiffGraph:
    changes = [
        ASTChange(
            file_path="test.py",
            change_type=ChangeType.ADDED,
            node_type="function_definition",
            name=name,
        )
        for name in names
    ]
    return DiffGraph(
        files_changed=files or ["test.py"],
        ast_changes=changes,
    )


class TestHeuristicAlignment:
    def test_matching_symbol_names(self):
        intent = _make_intent(["Add authenticate function"])
        diff = _make_diff(["authenticate"])
        findings, verified, unverifiable = verify_alignment(intent, diff)
        assert verified == 1
        assert unverifiable == 0

    def test_no_matching_symbols(self):
        intent = _make_intent(["Add payment processing"])
        diff = _make_diff(["validate_email"])
        findings, verified, unverifiable = verify_alignment(intent, diff)
        assert verified == 0
        assert unverifiable == 1
        assert len(findings) >= 1

    def test_file_path_matching(self):
        intent = _make_intent(["Update auth module"])
        diff = _make_diff(["some_func"], files=["auth.py"])
        findings, verified, unverifiable = verify_alignment(intent, diff)
        assert verified == 1

    def test_empty_claims(self):
        intent = IntentGraph(claims=[])
        diff = _make_diff(["func"])
        findings, verified, unverifiable = verify_alignment(intent, diff)
        assert verified == 0
        assert unverifiable == 0
        assert findings == []

    def test_low_confidence_no_finding(self):
        """LOW confidence unverifiable claims don't generate findings."""
        intent = _make_intent(["something vague"], confidence=Confidence.LOW)
        diff = _make_diff(["unrelated_func"])
        findings, verified, unverifiable = verify_alignment(intent, diff)
        assert unverifiable == 1
        assert len(findings) == 0  # LOW confidence = no finding

    def test_medium_confidence_generates_finding(self):
        intent = _make_intent(["Add payment gateway"], confidence=Confidence.MEDIUM)
        diff = _make_diff(["validate_email"])
        findings, verified, unverifiable = verify_alignment(intent, diff)
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.MEDIUM

    def test_multiple_claims_mixed(self):
        intent = _make_intent([
            "Add authenticate function",
            "Add unrelated payment thing",
        ])
        diff = _make_diff(["authenticate", "validate"])
        findings, verified, unverifiable = verify_alignment(intent, diff)
        assert verified >= 1
