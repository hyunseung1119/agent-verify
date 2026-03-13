"""Verification report data models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    """A single verification finding."""

    id: str
    severity: FindingSeverity
    category: str  # "missing_behavior", "silent_failure", "intent_mismatch", etc.
    title: str
    description: str
    file_path: str | None = None
    line_range: tuple[int, int] | None = None
    related_claim_id: str | None = None
    suggestion: str | None = None
    evidence: str = ""

    model_config = {"frozen": True}


class MutationResult(BaseModel):
    """Results from mutation testing."""

    total_mutants: int = 0
    killed: int = 0
    survived: int = 0
    timeout: int = 0

    @property
    def kill_rate(self) -> float:
        if self.total_mutants == 0:
            return 0.0
        return self.killed / self.total_mutants

    model_config = {"frozen": True}


class VerifyReport(BaseModel):
    """Complete verification report for a code change."""

    verdict: Verdict
    confidence_score: float = 0.0
    findings: list[Finding] = Field(default_factory=list)
    claims_verified: int = 0
    claims_total: int = 0
    claims_unverifiable: int = 0
    mutation_result: MutationResult | None = None
    execution_time_seconds: float = 0.0
    pipeline_version: str = "0.1.0"
    metadata: dict = Field(default_factory=dict)

    @property
    def critical_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == FindingSeverity.CRITICAL]

    @property
    def has_failures(self) -> bool:
        return self.verdict == Verdict.FAIL or len(self.critical_findings) > 0

    def to_summary(self) -> str:
        icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "inconclusive": "???"}
        lines = [
            f"[{icon[self.verdict.value]}] Verification Report",
            f"  Confidence: {self.confidence_score:.0%}",
            f"  Claims: {self.claims_verified}/{self.claims_total} verified",
            f"  Findings: {len(self.findings)} ({len(self.critical_findings)} critical)",
        ]
        if self.mutation_result:
            lines.append(f"  Mutation kill rate: {self.mutation_result.kill_rate:.0%}")
        return "\n".join(lines)
