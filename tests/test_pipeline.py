"""Tests for the verification pipeline."""

from __future__ import annotations

from agent_verify.models.diff import DiffGraph
from agent_verify.models.intent import Confidence, IntentClaim, IntentGraph, IntentType
from agent_verify.models.report import Finding, FindingSeverity, Verdict
from agent_verify.pipeline import _compute_confidence, _compute_verdict


class TestComputeConfidence:
    def _make_intent(self, n_claims: int = 3, n_high: int = 1) -> IntentGraph:
        claims = []
        for i in range(n_claims):
            conf = Confidence.HIGH if i < n_high else Confidence.MEDIUM
            claims.append(
                IntentClaim(
                    id=f"c{i}",
                    description=f"claim {i}",
                    type=IntentType.FEATURE,
                    source="test",
                    confidence=conf,
                )
            )
        return IntentGraph(claims=claims)

    def test_all_verified(self):
        intent = self._make_intent(3, 2)
        diff = DiffGraph()
        score = _compute_confidence(intent, diff, [], verified=3)
        assert score > 0.8

    def test_none_verified(self):
        intent = self._make_intent(3)
        diff = DiffGraph()
        score = _compute_confidence(intent, diff, [], verified=0)
        assert score < 0.2

    def test_no_claims(self):
        intent = IntentGraph()
        diff = DiffGraph()
        score = _compute_confidence(intent, diff, [], verified=0)
        assert score == 0.3

    def test_critical_finding_reduces_confidence(self):
        intent = self._make_intent(3)
        diff = DiffGraph()
        findings = [
            Finding(
                id="f1",
                severity=FindingSeverity.CRITICAL,
                category="test",
                title="bad",
                description="bad",
            ),
        ]
        score = _compute_confidence(intent, diff, findings, verified=3)
        assert score < 0.8

    def test_high_findings_reduce_confidence(self):
        intent = self._make_intent(3)
        diff = DiffGraph()
        findings = [
            Finding(
                id=f"f{i}",
                severity=FindingSeverity.HIGH,
                category="test",
                title="warn",
                description="warn",
            )
            for i in range(3)
        ]
        score = _compute_confidence(intent, diff, findings, verified=3)
        base_score = _compute_confidence(intent, diff, [], verified=3)
        assert score < base_score

    def test_high_confidence_claims_boost(self):
        intent_high = self._make_intent(3, n_high=3)
        intent_low = self._make_intent(3, n_high=0)
        diff = DiffGraph()
        score_high = _compute_confidence(intent_high, diff, [], verified=2)
        score_low = _compute_confidence(intent_low, diff, [], verified=2)
        assert score_high >= score_low


class TestComputeVerdict:
    def test_pass(self):
        verdict = _compute_verdict([], confidence=0.9, claims_total=3, claims_verified=3)
        assert verdict == Verdict.PASS

    def test_fail_on_critical(self):
        findings = [
            Finding(
                id="f1",
                severity=FindingSeverity.CRITICAL,
                category="test",
                title="bad",
                description="bad",
            ),
        ]
        verdict = _compute_verdict(findings, confidence=0.9, claims_total=3, claims_verified=3)
        assert verdict == Verdict.FAIL

    def test_fail_on_many_high(self):
        findings = [
            Finding(
                id=f"f{i}",
                severity=FindingSeverity.HIGH,
                category="test",
                title="warn",
                description="warn",
            )
            for i in range(3)
        ]
        verdict = _compute_verdict(findings, confidence=0.9, claims_total=3, claims_verified=3)
        assert verdict == Verdict.FAIL

    def test_warn_on_high(self):
        findings = [
            Finding(
                id="f1",
                severity=FindingSeverity.HIGH,
                category="test",
                title="warn",
                description="warn",
            ),
        ]
        verdict = _compute_verdict(findings, confidence=0.9, claims_total=3, claims_verified=3)
        assert verdict == Verdict.WARN

    def test_warn_on_low_confidence(self):
        verdict = _compute_verdict([], confidence=0.5, claims_total=3, claims_verified=1)
        assert verdict == Verdict.WARN

    def test_inconclusive_on_very_low_confidence(self):
        verdict = _compute_verdict([], confidence=0.2, claims_total=3, claims_verified=0)
        assert verdict == Verdict.INCONCLUSIVE
