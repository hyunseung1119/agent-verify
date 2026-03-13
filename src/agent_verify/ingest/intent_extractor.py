"""Main intent extraction orchestrator."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

from agent_verify.models.intent import Confidence, IntentClaim, IntentGraph, IntentType


class IntentSource(Protocol):
    """Protocol for intent extraction sources."""

    def source_name(self) -> str: ...
    def extract(self, context: dict) -> list[IntentClaim]: ...


# --- Conventional Commit Parsing ---

_COMMIT_TYPE_MAP = {
    "feat": IntentType.FEATURE,
    "fix": IntentType.BUGFIX,
    "refactor": IntentType.REFACTOR,
    "perf": IntentType.PERFORMANCE,
    "security": IntentType.SECURITY,
}

_COMMIT_PATTERN = re.compile(
    r"^(?P<type>feat|fix|refactor|perf|security|docs|test|chore|ci|style|build)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"!?:\s*(?P<description>.+)$",
    re.MULTILINE,
)


class CommitMessageSource:
    """Extracts intent from conventional commit messages."""

    def source_name(self) -> str:
        return "commit_message"

    def extract(self, context: dict) -> list[IntentClaim]:
        commits = context.get("commits", [])
        if isinstance(commits, str):
            commits = [{"message": commits}]

        claims: list[IntentClaim] = []
        for commit in commits:
            msg = commit if isinstance(commit, str) else commit.get("message", "")
            match = _COMMIT_PATTERN.match(msg.strip())
            if not match:
                continue

            commit_type = match.group("type")
            scope = match.group("scope") or ""
            description = match.group("description").strip()

            intent_type = _COMMIT_TYPE_MAP.get(commit_type)
            if intent_type is None:
                continue

            claim_id = _make_id(f"commit:{msg[:80]}")
            claims.append(IntentClaim(
                id=claim_id,
                description=f"{description}" + (f" (scope: {scope})" if scope else ""),
                type=intent_type,
                source="commit_message",
                source_text=msg,
                confidence=Confidence.MEDIUM,
            ))

        return claims


# --- PR Description Parsing ---

_SECTION_HEADERS = re.compile(
    r"^##\s*(what|summary|changes|description|why|acceptance\s*criteria|test\s*plan)",
    re.IGNORECASE | re.MULTILINE,
)


class PRDescriptionSource:
    """Extracts intent from PR/MR descriptions."""

    def source_name(self) -> str:
        return "pr_description"

    def extract(self, context: dict) -> list[IntentClaim]:
        pr_body = context.get("pr_body", "")
        if not pr_body or not pr_body.strip():
            return []

        claims: list[IntentClaim] = []
        sections = self._parse_sections(pr_body)

        for section_name, content in sections.items():
            bullets = self._extract_bullets(content)
            for bullet in bullets:
                if len(bullet) < 10:
                    continue
                claim_id = _make_id(f"pr:{bullet[:80]}")
                claims.append(IntentClaim(
                    id=claim_id,
                    description=bullet,
                    type=self._infer_type(bullet, section_name),
                    source="pr_description",
                    source_text=bullet,
                    confidence=Confidence.HIGH if section_name else Confidence.MEDIUM,
                ))

        # If no structured sections, treat entire body as description
        if not claims and pr_body.strip():
            sentences = self._extract_sentences(pr_body)
            for sentence in sentences[:5]:
                if len(sentence) < 10:
                    continue
                claim_id = _make_id(f"pr:{sentence[:80]}")
                claims.append(IntentClaim(
                    id=claim_id,
                    description=sentence,
                    type=self._infer_type(sentence, ""),
                    source="pr_description",
                    source_text=sentence,
                    confidence=Confidence.MEDIUM,
                ))

        return claims

    def _parse_sections(self, body: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        current_section = ""
        current_content: list[str] = []

        for line in body.split("\n"):
            header_match = _SECTION_HEADERS.match(line.strip())
            if header_match:
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content)
                current_section = header_match.group(1).lower().strip()
                current_content = []
            else:
                current_content.append(line)

        if current_section and current_content:
            sections[current_section] = "\n".join(current_content)

        return sections

    def _extract_bullets(self, text: str) -> list[str]:
        bullets: list[str] = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("- ", "* ", "• ")):
                bullet = stripped.lstrip("-*• ").strip()
                if bullet:
                    bullets.append(bullet)
        return bullets

    def _extract_sentences(self, text: str) -> list[str]:
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`[^`]+`", "", text)
        text = re.sub(r"#+ ", "", text)
        sentences = re.split(r"[.!?\n]", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _infer_type(self, text: str, section: str) -> IntentType:
        lower = text.lower()
        if any(w in lower for w in ["fix", "bug", "error", "crash", "issue"]):
            return IntentType.BUGFIX
        if any(w in lower for w in ["refactor", "clean", "reorganize", "rename"]):
            return IntentType.REFACTOR
        if any(w in lower for w in ["performance", "speed", "optimize", "cache", "latency"]):
            return IntentType.PERFORMANCE
        if any(w in lower for w in ["security", "auth", "xss", "injection", "csrf"]):
            return IntentType.SECURITY
        return IntentType.FEATURE


# --- Spec File Parsing ---

class SpecFileSource:
    """Extracts intent from SPEC.md, RFC files."""

    def source_name(self) -> str:
        return "spec_file"

    def extract(self, context: dict) -> list[IntentClaim]:
        spec_content = context.get("spec_content", "")
        if not spec_content:
            return []

        claims: list[IntentClaim] = []
        bullets = _extract_all_bullets(spec_content)

        for bullet in bullets:
            if len(bullet) < 10:
                continue
            claim_id = _make_id(f"spec:{bullet[:80]}")
            claims.append(IntentClaim(
                id=claim_id,
                description=bullet,
                type=_infer_type_generic(bullet),
                source="spec_file",
                source_text=bullet,
                confidence=Confidence.HIGH,
            ))

        return claims


# --- Orchestrator ---

def extract_intent(context: dict, sources: list[IntentSource] | None = None) -> IntentGraph:
    """Extract intent from all available sources."""
    if sources is None:
        sources = [
            SpecFileSource(),
            PRDescriptionSource(),
            CommitMessageSource(),
        ]

    all_claims: list[IntentClaim] = []
    raw_sources: dict[str, str] = {}

    for source in sources:
        claims = source.extract(context)
        all_claims.extend(claims)
        name = source.source_name()
        raw_sources[name] = context.get(name, context.get("pr_body", ""))

    deduplicated = _deduplicate(all_claims)

    return IntentGraph(
        claims=deduplicated,
        raw_sources=raw_sources,
    )


# --- Helpers ---

def _make_id(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _deduplicate(claims: list[IntentClaim]) -> list[IntentClaim]:
    seen: set[str] = set()
    result: list[IntentClaim] = []
    for claim in claims:
        key = claim.description.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(claim)
    return result


def _extract_all_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "• ")):
            bullet = stripped.lstrip("-*• ").strip()
            if bullet:
                bullets.append(bullet)
    return bullets


def _infer_type_generic(text: str) -> IntentType:
    lower = text.lower()
    if any(w in lower for w in ["fix", "bug", "error"]):
        return IntentType.BUGFIX
    if any(w in lower for w in ["refactor", "clean"]):
        return IntentType.REFACTOR
    if any(w in lower for w in ["perf", "speed", "optim"]):
        return IntentType.PERFORMANCE
    if any(w in lower for w in ["secur", "auth", "xss"]):
        return IntentType.SECURITY
    return IntentType.FEATURE
