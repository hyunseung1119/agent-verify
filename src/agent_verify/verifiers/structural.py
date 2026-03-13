"""Structural verification: does the code structure match the intent?"""

from __future__ import annotations

from agent_verify.models.diff import ASTChange, ChangeType, DiffGraph
from agent_verify.models.intent import IntentClaim, IntentGraph, IntentType
from agent_verify.models.report import Finding, FindingSeverity


def verify_structural(intent: IntentGraph, diff: DiffGraph) -> list[Finding]:
    """Verify code structure against intent claims."""
    findings: list[Finding] = []

    findings.extend(_check_feature_claims_have_additions(intent, diff))
    findings.extend(_check_bugfix_claims_have_modifications(intent, diff))
    findings.extend(_check_removed_code_safety(diff))
    findings.extend(_check_scope_creep(intent, diff))

    return findings


def _check_feature_claims_have_additions(
    intent: IntentGraph, diff: DiffGraph
) -> list[Finding]:
    """Feature claims should result in new code being added."""
    findings: list[Finding] = []
    feature_claims = [c for c in intent.claims if c.type == IntentType.FEATURE]

    if not feature_claims:
        return findings

    added = [c for c in diff.ast_changes if c.change_type == ChangeType.ADDED]

    if feature_claims and not added:
        findings.append(Finding(
            id="struct-001",
            severity=FindingSeverity.HIGH,
            category="missing_behavior",
            title="Feature claim but no new code added",
            description=(
                f"{len(feature_claims)} feature claim(s) found, "
                f"but no new functions/classes were added. "
                f"Claims: {', '.join(c.description[:60] for c in feature_claims[:3])}"
            ),
            evidence="AST diff shows 0 added definitions",
            suggestion="Verify that the feature was implemented, not just configured",
        ))

    return findings


def _check_bugfix_claims_have_modifications(
    intent: IntentGraph, diff: DiffGraph
) -> list[Finding]:
    """Bug fix claims should modify existing code, not just add new code."""
    findings: list[Finding] = []
    bugfix_claims = [c for c in intent.claims if c.type == IntentType.BUGFIX]

    if not bugfix_claims:
        return findings

    modified = [c for c in diff.ast_changes if c.change_type == ChangeType.MODIFIED]

    if bugfix_claims and not modified:
        findings.append(Finding(
            id="struct-002",
            severity=FindingSeverity.MEDIUM,
            category="intent_mismatch",
            title="Bug fix claim but no existing code modified",
            description=(
                f"{len(bugfix_claims)} bug fix claim(s) found, "
                f"but no existing functions were modified. "
                f"Was the fix to add new code rather than fix existing code?"
            ),
            evidence="AST diff shows 0 modified definitions",
        ))

    return findings


def _check_removed_code_safety(diff: DiffGraph) -> list[Finding]:
    """Warn when code is removed without clear intent to do so."""
    findings: list[Finding] = []
    removed = [c for c in diff.ast_changes if c.change_type == ChangeType.REMOVED]

    for change in removed:
        findings.append(Finding(
            id=f"struct-003-{change.name}",
            severity=FindingSeverity.MEDIUM,
            category="silent_failure",
            title=f"Code removed: {change.name}",
            description=(
                f"{change.node_type} '{change.name}' was removed from {change.file_path}. "
                f"Verify this removal was intentional and doesn't break callers."
            ),
            file_path=change.file_path,
            line_range=(change.start_line, change.end_line),
            evidence=f"Old signature: {change.old_signature or 'N/A'}",
            suggestion="Check for remaining references to this symbol",
        ))

    return findings


def _check_scope_creep(intent: IntentGraph, diff: DiffGraph) -> list[Finding]:
    """Detect when changes are much broader than the stated intent."""
    findings: list[Finding] = []

    if not intent.claims:
        return findings

    claim_count = len(intent.claims)
    change_count = diff.change_count

    if change_count > claim_count * 5 and change_count > 10:
        findings.append(Finding(
            id="struct-004",
            severity=FindingSeverity.LOW,
            category="scope_creep",
            title="Changes significantly broader than stated intent",
            description=(
                f"{claim_count} intent claim(s) but {change_count} AST changes detected. "
                f"This may indicate scope creep or undocumented changes."
            ),
            evidence=f"Ratio: {change_count / claim_count:.1f}x changes per claim",
            suggestion="Consider documenting additional changes in the PR description",
        ))

    return findings
