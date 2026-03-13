"""Intent extraction data models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    PERFORMANCE = "performance"
    SECURITY = "security"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IntentClaim(BaseModel):
    """A single atomic, testable claim about what a code change should do."""

    id: str
    description: str
    type: IntentType
    source: str  # "pr_description", "commit_message", "spec_file", "inline_comment"
    source_text: str = ""
    confidence: Confidence
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    negative_conditions: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class IntentGraph(BaseModel):
    """All extracted intent claims for a code change."""

    claims: list[IntentClaim] = Field(default_factory=list)
    raw_sources: dict[str, str] = Field(default_factory=dict)
    extraction_model: str = ""

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    @property
    def high_confidence_claims(self) -> list[IntentClaim]:
        return [c for c in self.claims if c.confidence == Confidence.HIGH]

    def get_claim(self, claim_id: str) -> IntentClaim | None:
        return next((c for c in self.claims if c.id == claim_id), None)
