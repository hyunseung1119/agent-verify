"""Tests for structural verification."""

from __future__ import annotations

from agent_verify.models.diff import ASTChange, ChangeType, DiffGraph
from agent_verify.models.intent import Confidence, IntentClaim, IntentGraph, IntentType
from agent_verify.models.report import FindingSeverity
from agent_verify.verifiers.structural import verify_structural


def _make_claim(
    desc: str = "test claim",
    type_: IntentType = IntentType.FEATURE,
    confidence: Confidence = Confidence.MEDIUM,
) -> IntentClaim:
    return IntentClaim(
        id="test-001",
        description=desc,
        type=type_,
        source="test",
        confidence=confidence,
    )


def _make_change(
    name: str = "func",
    change_type: ChangeType = ChangeType.ADDED,
    file_path: str = "test.py",
) -> ASTChange:
    return ASTChange(
        file_path=file_path,
        change_type=change_type,
        node_type="function_definition",
        name=name,
    )


class TestFeatureClaimsHaveAdditions:
    def test_feature_with_additions_passes(self):
        intent = IntentGraph(claims=[_make_claim(type_=IntentType.FEATURE)])
        diff = DiffGraph(
            files_changed=["test.py"],
            ast_changes=[_make_change(change_type=ChangeType.ADDED)],
        )
        findings = verify_structural(intent, diff)
        feature_findings = [f for f in findings if f.id == "struct-001"]
        assert len(feature_findings) == 0

    def test_feature_without_additions_warns(self):
        intent = IntentGraph(claims=[_make_claim(type_=IntentType.FEATURE)])
        diff = DiffGraph(
            files_changed=["test.py"],
            ast_changes=[_make_change(change_type=ChangeType.MODIFIED)],
        )
        findings = verify_structural(intent, diff)
        feature_findings = [f for f in findings if f.id == "struct-001"]
        assert len(feature_findings) == 1
        assert feature_findings[0].severity == FindingSeverity.HIGH


class TestBugfixClaimsHaveModifications:
    def test_bugfix_with_modifications_passes(self):
        intent = IntentGraph(claims=[_make_claim(type_=IntentType.BUGFIX)])
        diff = DiffGraph(
            files_changed=["test.py"],
            ast_changes=[_make_change(change_type=ChangeType.MODIFIED)],
        )
        findings = verify_structural(intent, diff)
        bugfix_findings = [f for f in findings if f.id == "struct-002"]
        assert len(bugfix_findings) == 0

    def test_bugfix_without_modifications_warns(self):
        intent = IntentGraph(claims=[_make_claim(type_=IntentType.BUGFIX)])
        diff = DiffGraph(
            files_changed=["test.py"],
            ast_changes=[_make_change(change_type=ChangeType.ADDED)],
        )
        findings = verify_structural(intent, diff)
        bugfix_findings = [f for f in findings if f.id == "struct-002"]
        assert len(bugfix_findings) == 1
        assert bugfix_findings[0].severity == FindingSeverity.MEDIUM


class TestRemovedCodeSafety:
    def test_removed_code_generates_finding(self):
        intent = IntentGraph(claims=[])
        diff = DiffGraph(
            files_changed=["test.py"],
            ast_changes=[_make_change(name="old_func", change_type=ChangeType.REMOVED)],
        )
        findings = verify_structural(intent, diff)
        removal_findings = [f for f in findings if "struct-003" in f.id]
        assert len(removal_findings) == 1
        assert "old_func" in removal_findings[0].title


class TestScopeCreep:
    def test_no_scope_creep(self):
        intent = IntentGraph(claims=[_make_claim()])
        diff = DiffGraph(
            files_changed=["test.py"],
            ast_changes=[_make_change()],
        )
        findings = verify_structural(intent, diff)
        scope_findings = [f for f in findings if f.id == "struct-004"]
        assert len(scope_findings) == 0

    def test_scope_creep_detected(self):
        claims = [_make_claim()]
        changes = [
            _make_change(name=f"func_{i}", change_type=ChangeType.MODIFIED)
            for i in range(15)
        ]
        intent = IntentGraph(claims=claims)
        diff = DiffGraph(files_changed=["test.py"], ast_changes=changes)
        findings = verify_structural(intent, diff)
        scope_findings = [f for f in findings if f.id == "struct-004"]
        assert len(scope_findings) == 1
        assert scope_findings[0].severity == FindingSeverity.LOW

    def test_no_claims_no_scope_creep(self):
        intent = IntentGraph(claims=[])
        diff = DiffGraph(
            files_changed=["test.py"],
            ast_changes=[_make_change() for _ in range(20)],
        )
        findings = verify_structural(intent, diff)
        scope_findings = [f for f in findings if f.id == "struct-004"]
        assert len(scope_findings) == 0
