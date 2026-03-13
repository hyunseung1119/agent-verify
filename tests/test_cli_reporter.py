"""Tests for the CLI reporter output."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from agent_verify.models.report import Finding, FindingSeverity, Verdict, VerifyReport
from agent_verify.output.cli_reporter import print_report


class TestPrintReport:
    def _capture(self, report: VerifyReport) -> str:
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        print_report(report, console)
        return buf.getvalue()

    def test_pass_verdict(self):
        report = VerifyReport(
            verdict=Verdict.PASS,
            confidence_score=0.95,
            claims_verified=3,
            claims_total=3,
        )
        output = self._capture(report)
        assert "PASS" in output
        assert "3/3" in output

    def test_fail_verdict(self):
        report = VerifyReport(
            verdict=Verdict.FAIL,
            confidence_score=0.1,
        )
        output = self._capture(report)
        assert "FAIL" in output

    def test_findings_displayed(self):
        report = VerifyReport(
            verdict=Verdict.WARN,
            confidence_score=0.6,
            findings=[
                Finding(
                    id="f1",
                    severity=FindingSeverity.HIGH,
                    category="intent_mismatch",
                    title="Claim not verified",
                    description="Details here",
                    suggestion="Check the code",
                ),
                Finding(
                    id="f2",
                    severity=FindingSeverity.LOW,
                    category="scope_creep",
                    title="Extra changes",
                    description="Minor issue",
                ),
            ],
        )
        output = self._capture(report)
        assert "Claim not verified" in output
        assert "Check the code" in output

    def test_no_findings(self):
        report = VerifyReport(
            verdict=Verdict.PASS,
            confidence_score=0.9,
        )
        output = self._capture(report)
        assert "PASS" in output

    def test_inconclusive(self):
        report = VerifyReport(
            verdict=Verdict.INCONCLUSIVE,
            confidence_score=0.2,
        )
        output = self._capture(report)
        assert "???" in output

    def test_default_console(self):
        report = VerifyReport(verdict=Verdict.PASS, confidence_score=0.9)
        # Should not raise
        print_report(report)
