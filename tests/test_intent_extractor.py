"""Tests for intent extraction from various sources."""

from __future__ import annotations

from agent_verify.ingest.intent_extractor import (
    CommitMessageSource,
    PRDescriptionSource,
    SpecFileSource,
    extract_intent,
)
from agent_verify.models.intent import Confidence, IntentType


class TestCommitMessageSource:
    """Tests for conventional commit parsing."""

    def test_feat_commit(self):
        source = CommitMessageSource()
        claims = source.extract({"commits": ["feat: add user authentication"]})
        assert len(claims) == 1
        assert claims[0].type == IntentType.FEATURE
        assert "add user authentication" in claims[0].description

    def test_fix_commit(self):
        source = CommitMessageSource()
        claims = source.extract({"commits": ["fix: resolve null pointer in parser"]})
        assert len(claims) == 1
        assert claims[0].type == IntentType.BUGFIX

    def test_scoped_commit(self):
        source = CommitMessageSource()
        claims = source.extract({"commits": ["feat(auth): add OAuth2 support"]})
        assert len(claims) == 1
        assert "scope: auth" in claims[0].description

    def test_refactor_commit(self):
        source = CommitMessageSource()
        claims = source.extract({"commits": ["refactor: extract validation logic"]})
        assert len(claims) == 1
        assert claims[0].type == IntentType.REFACTOR

    def test_perf_commit(self):
        source = CommitMessageSource()
        claims = source.extract({"commits": ["perf: optimize database queries"]})
        assert len(claims) == 1
        assert claims[0].type == IntentType.PERFORMANCE

    def test_non_conventional_commit_ignored(self):
        source = CommitMessageSource()
        claims = source.extract({"commits": ["updated some stuff"]})
        assert len(claims) == 0

    def test_docs_commit_ignored(self):
        """docs/test/chore/ci commits don't map to intent types."""
        source = CommitMessageSource()
        claims = source.extract({"commits": ["docs: update README"]})
        assert len(claims) == 0

    def test_multiple_commits(self):
        source = CommitMessageSource()
        commits = [
            "feat: add login endpoint",
            "fix: handle empty username",
            "docs: update API docs",
        ]
        claims = source.extract({"commits": commits})
        assert len(claims) == 2  # docs is excluded

    def test_empty_commits(self):
        source = CommitMessageSource()
        assert source.extract({"commits": []}) == []
        assert source.extract({}) == []

    def test_confidence_is_medium(self):
        source = CommitMessageSource()
        claims = source.extract({"commits": ["feat: add thing"]})
        assert claims[0].confidence == Confidence.MEDIUM

    def test_source_name(self):
        assert CommitMessageSource().source_name() == "commit_message"


class TestPRDescriptionSource:
    """Tests for PR description parsing."""

    def test_structured_pr_with_sections(self):
        source = PRDescriptionSource()
        pr_body = """## What
- Add user authentication via OAuth2
- Support Google and GitHub providers

## Changes
- New auth middleware
- Token refresh mechanism
"""
        claims = source.extract({"pr_body": pr_body})
        assert len(claims) >= 2
        assert all(c.confidence == Confidence.HIGH for c in claims)

    def test_unstructured_pr_body(self):
        source = PRDescriptionSource()
        pr_body = "This PR adds a new caching layer to improve API response times"
        claims = source.extract({"pr_body": pr_body})
        assert len(claims) >= 1

    def test_empty_pr_body(self):
        source = PRDescriptionSource()
        assert source.extract({"pr_body": ""}) == []
        assert source.extract({}) == []

    def test_bugfix_keyword_detection(self):
        source = PRDescriptionSource()
        pr_body = "## What\n- Fix crash when user submits empty form"
        claims = source.extract({"pr_body": pr_body})
        assert claims[0].type == IntentType.BUGFIX

    def test_refactor_keyword_detection(self):
        source = PRDescriptionSource()
        pr_body = "## Changes\n- Refactor authentication module for clarity"
        claims = source.extract({"pr_body": pr_body})
        assert claims[0].type == IntentType.REFACTOR

    def test_performance_keyword_detection(self):
        source = PRDescriptionSource()
        pr_body = "## What\n- Optimize database query for faster page loads"
        claims = source.extract({"pr_body": pr_body})
        assert claims[0].type == IntentType.PERFORMANCE

    def test_security_keyword_detection(self):
        source = PRDescriptionSource()
        pr_body = "## What\n- Patch XSS vulnerability in comment rendering"
        claims = source.extract({"pr_body": pr_body})
        assert claims[0].type == IntentType.SECURITY

    def test_short_bullets_ignored(self):
        source = PRDescriptionSource()
        pr_body = "## What\n- OK\n- This is a real change description"
        claims = source.extract({"pr_body": pr_body})
        # "OK" is < 10 chars, should be skipped
        assert all(len(c.description) >= 10 for c in claims)

    def test_source_name(self):
        assert PRDescriptionSource().source_name() == "pr_description"


class TestSpecFileSource:
    """Tests for spec file parsing."""

    def test_spec_bullets(self):
        source = SpecFileSource()
        spec = """# Feature Spec
- Implement rate limiting for API endpoints
- Add Redis-based token bucket algorithm
- Support per-user rate limits
"""
        claims = source.extract({"spec_content": spec})
        assert len(claims) == 3
        assert all(c.confidence == Confidence.HIGH for c in claims)
        assert all(c.source == "spec_file" for c in claims)

    def test_empty_spec(self):
        source = SpecFileSource()
        assert source.extract({"spec_content": ""}) == []
        assert source.extract({}) == []

    def test_source_name(self):
        assert SpecFileSource().source_name() == "spec_file"


class TestExtractIntent:
    """Tests for the orchestrator."""

    def test_combines_multiple_sources(self):
        context = {
            "commits": ["feat: add caching layer"],
            "pr_body": "## What\n- Add Redis-based caching for API responses",
        }
        intent = extract_intent(context)
        assert intent.claim_count >= 2

    def test_deduplicates_claims(self):
        context = {
            "commits": ["feat: add caching layer"],
            "pr_body": "## What\n- add caching layer",
        }
        intent = extract_intent(context)
        # Same description (case-insensitive) should be deduplicated
        descriptions = [c.description.lower().strip() for c in intent.claims]
        assert len(descriptions) == len(set(descriptions))

    def test_empty_context(self):
        intent = extract_intent({})
        assert intent.claim_count == 0
        assert intent.claims == []

    def test_high_confidence_claims_property(self):
        context = {
            "spec_content": "- Implement OAuth2 authentication flow",
            "commits": ["feat: add OAuth2"],
        }
        intent = extract_intent(context)
        # Spec claims are HIGH confidence
        assert len(intent.high_confidence_claims) >= 1

    def test_get_claim_by_id(self):
        context = {"commits": ["feat: add search endpoint"]}
        intent = extract_intent(context)
        if intent.claims:
            claim = intent.get_claim(intent.claims[0].id)
            assert claim is not None
            assert claim.id == intent.claims[0].id

    def test_get_claim_not_found(self):
        intent = extract_intent({})
        assert intent.get_claim("nonexistent") is None
