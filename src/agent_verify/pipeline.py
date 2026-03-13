"""Main verification pipeline orchestrator."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from agent_verify.analyzers.ast_differ import build_diff_graph, detect_language
from agent_verify.ingest.intent_extractor import extract_intent
from agent_verify.models.intent import IntentGraph
from agent_verify.models.diff import DiffGraph
from agent_verify.models.report import Finding, Verdict, VerifyReport
from agent_verify.verifiers.structural import verify_structural
from agent_verify.verifiers.alignment import verify_alignment


def run_pipeline(
    diff_ref: str = "HEAD~1",
    pr_body: str = "",
    spec_file: str = "",
    repo_path: str = ".",
    use_llm: bool = False,
) -> VerifyReport:
    """
    Run the full verification pipeline.

    Args:
        diff_ref: Git ref to diff against (default: HEAD~1)
        pr_body: PR description text
        spec_file: Path to spec file (SPEC.md, RFC, etc.)
        repo_path: Path to the git repository
        use_llm: Whether to use LLM for spec-code alignment
    """
    start = time.monotonic()

    # 1. Gather context
    context = _build_context(diff_ref, pr_body, spec_file, repo_path)

    # 2. Extract intent
    intent = extract_intent(context)

    # 3. Build AST diff
    file_diffs = _get_file_diffs(diff_ref, repo_path)
    diff_graph = build_diff_graph(file_diffs)

    # 4. Run verifiers
    all_findings: list[Finding] = []

    # Structural verification
    structural_findings = verify_structural(intent, diff_graph)
    all_findings.extend(structural_findings)

    # Alignment verification
    code_contents = {fd["file_path"]: fd["new_content"] for fd in file_diffs}
    alignment_findings, verified, unverifiable = verify_alignment(
        intent, diff_graph, code_contents, use_llm=use_llm
    )
    all_findings.extend(alignment_findings)

    # 5. Compute verdict
    claims_total = intent.claim_count
    claims_verified = verified
    confidence = _compute_confidence(intent, diff_graph, all_findings, verified)
    verdict = _compute_verdict(all_findings, confidence, claims_total, verified)

    elapsed = time.monotonic() - start

    return VerifyReport(
        verdict=verdict,
        confidence_score=confidence,
        findings=all_findings,
        claims_verified=claims_verified,
        claims_total=claims_total,
        claims_unverifiable=unverifiable,
        execution_time_seconds=round(elapsed, 2),
        metadata={
            "diff_ref": diff_ref,
            "files_changed": diff_graph.files_changed,
            "languages": diff_graph.languages_detected,
        },
    )


def _build_context(
    diff_ref: str, pr_body: str, spec_file: str, repo_path: str
) -> dict:
    """Build context dict for intent extraction."""
    context: dict = {}

    # PR body
    if pr_body:
        context["pr_body"] = pr_body

    # Spec file
    if spec_file:
        spec_path = Path(spec_file)
        if spec_path.exists():
            context["spec_content"] = spec_path.read_text(encoding="utf-8")

    # Commit messages
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--format=%s", f"{diff_ref}..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            commits = [msg.strip() for msg in result.stdout.strip().split("\n") if msg.strip()]
            context["commits"] = commits
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return context


def _get_file_diffs(diff_ref: str, repo_path: str) -> list[dict[str, str]]:
    """Get file-level diffs from git."""
    file_diffs: list[dict[str, str]] = []

    try:
        # Get list of changed files
        result = subprocess.run(
            ["git", "-C", repo_path, "diff", "--name-only", diff_ref],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return file_diffs

        changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        for file_path in changed_files:
            lang = detect_language(file_path)
            if lang is None:
                continue

            full_path = Path(repo_path) / file_path

            # Get old content
            old_result = subprocess.run(
                ["git", "-C", repo_path, "show", f"{diff_ref}:{file_path}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            old_content = old_result.stdout if old_result.returncode == 0 else ""

            # Get new content
            new_content = ""
            if full_path.exists():
                try:
                    new_content = full_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue

            file_diffs.append({
                "file_path": file_path,
                "old_content": old_content,
                "new_content": new_content,
            })

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return file_diffs


def _compute_confidence(
    intent: IntentGraph,
    diff: DiffGraph,
    findings: list[Finding],
    verified: int,
) -> float:
    """Compute overall confidence score (0.0 - 1.0)."""
    if intent.claim_count == 0:
        return 0.3  # No claims = low confidence

    base = verified / intent.claim_count if intent.claim_count > 0 else 0.0

    # Penalize for critical/high findings
    from agent_verify.models.report import FindingSeverity
    critical = sum(1 for f in findings if f.severity == FindingSeverity.CRITICAL)
    high = sum(1 for f in findings if f.severity == FindingSeverity.HIGH)
    penalty = critical * 0.3 + high * 0.1

    # Boost for high-confidence claims
    high_conf_ratio = (
        len(intent.high_confidence_claims) / intent.claim_count
        if intent.claim_count > 0
        else 0
    )
    boost = high_conf_ratio * 0.1

    return max(0.0, min(1.0, base - penalty + boost))


def _compute_verdict(
    findings: list[Finding],
    confidence: float,
    claims_total: int,
    claims_verified: int,
) -> Verdict:
    """Determine pass/warn/fail verdict."""
    from agent_verify.models.report import FindingSeverity

    critical = any(f.severity == FindingSeverity.CRITICAL for f in findings)
    high_count = sum(1 for f in findings if f.severity == FindingSeverity.HIGH)

    if critical:
        return Verdict.FAIL
    if high_count >= 3:
        return Verdict.FAIL
    if confidence < 0.3:
        return Verdict.INCONCLUSIVE
    if high_count > 0 or confidence < 0.6:
        return Verdict.WARN
    return Verdict.PASS
