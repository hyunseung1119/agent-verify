"""Spec-to-code alignment verification using LLM or heuristics."""

from __future__ import annotations

from agent_verify.models.diff import DiffGraph
from agent_verify.models.intent import Confidence, IntentClaim, IntentGraph
from agent_verify.models.report import Finding, FindingSeverity


def verify_alignment(
    intent: IntentGraph,
    diff: DiffGraph,
    code_contents: dict[str, str] | None = None,
    use_llm: bool = False,
) -> tuple[list[Finding], int, int]:
    """
    Verify alignment between intent claims and actual code.

    Returns: (findings, claims_verified, claims_unverifiable)
    """
    findings: list[Finding] = []
    verified = 0
    unverifiable = 0

    if not intent.claims:
        return findings, 0, 0

    if use_llm and code_contents:
        return _llm_alignment(intent, diff, code_contents)

    return _heuristic_alignment(intent, diff)


def _heuristic_alignment(
    intent: IntentGraph,
    diff: DiffGraph,
) -> tuple[list[Finding], int, int]:
    """Rule-based alignment check without LLM."""
    findings: list[Finding] = []
    verified = 0
    unverifiable = 0

    changed_names = {
        c.name.lower() for c in diff.ast_changes if c.name
    }
    changed_files = {f.lower() for f in diff.files_changed}

    for claim in intent.claims:
        desc_words = set(claim.description.lower().split())

        # Check if any changed symbol names appear in the claim
        name_overlap = desc_words & changed_names
        file_overlap = any(
            any(word in f for word in desc_words)
            for f in changed_files
        )

        if name_overlap or file_overlap:
            verified += 1
        elif claim.confidence == Confidence.LOW:
            unverifiable += 1
        else:
            unverifiable += 1
            findings.append(Finding(
                id=f"align-001-{claim.id[:8]}",
                severity=FindingSeverity.MEDIUM,
                category="intent_mismatch",
                title=f"Claim not traceable to code changes",
                description=(
                    f"Claim: \"{claim.description[:100]}\"\n"
                    f"No AST changes found that clearly correspond to this claim."
                ),
                related_claim_id=claim.id,
                evidence=f"Changed symbols: {', '.join(sorted(changed_names)[:5])}",
                suggestion="Verify this claim is addressed in the code changes",
            ))

    return findings, verified, unverifiable


def _llm_alignment(
    intent: IntentGraph,
    diff: DiffGraph,
    code_contents: dict[str, str],
) -> tuple[list[Finding], int, int]:
    """LLM-based alignment check (requires anthropic SDK)."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return _heuristic_alignment(intent, diff)

    findings: list[Finding] = []
    verified = 0
    unverifiable = 0

    # Build code context
    code_summary = ""
    for path, content in list(code_contents.items())[:5]:
        code_summary += f"\n--- {path} ---\n{content[:3000]}\n"

    client = Anthropic()

    for claim in intent.claims:
        prompt = (
            f"You are a code verification engine. Determine if the following code change "
            f"satisfies this intent claim.\n\n"
            f"CLAIM: {claim.description}\n"
            f"POSTCONDITIONS: {', '.join(claim.postconditions) or 'None specified'}\n"
            f"NEGATIVE CONDITIONS: {', '.join(claim.negative_conditions) or 'None specified'}\n\n"
            f"CODE CHANGES:\n{code_summary[:5000]}\n\n"
            f"Respond with exactly one of: VERIFIED, UNVERIFIED, INCONCLUSIVE\n"
            f"Then on the next line, explain your reasoning in 1-2 sentences."
        )

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response.content[0].text.strip()
            first_line = result_text.split("\n")[0].strip().upper()

            if "VERIFIED" in first_line and "UNVERIFIED" not in first_line:
                verified += 1
            elif "INCONCLUSIVE" in first_line:
                unverifiable += 1
            else:
                unverifiable += 1
                reasoning = "\n".join(result_text.split("\n")[1:]).strip()
                findings.append(Finding(
                    id=f"align-llm-{claim.id[:8]}",
                    severity=FindingSeverity.HIGH,
                    category="intent_mismatch",
                    title=f"LLM: Claim not verified in code",
                    description=(
                        f"Claim: \"{claim.description[:100]}\"\n"
                        f"LLM reasoning: {reasoning[:200]}"
                    ),
                    related_claim_id=claim.id,
                    evidence="LLM-based spec-code alignment check",
                ))
        except Exception:
            unverifiable += 1

    return findings, verified, unverifiable
