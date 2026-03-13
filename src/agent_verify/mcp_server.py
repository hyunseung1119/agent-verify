"""MCP server for agent-verify — exposes verification tools to Claude Code."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from agent_verify.analyzers.ast_differ import compute_ast_diff, detect_language
from agent_verify.ingest.intent_extractor import extract_intent
from agent_verify.pipeline import run_pipeline

mcp = FastMCP(
    "agent-verify",
    instructions="AI code verification engine — validates whether AI-generated code does what was intended",
)


def _serialize(obj: Any) -> Any:
    """Recursively serialize pydantic models and enums to plain dicts."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    return obj


@mcp.tool()
def verify_changes(
    diff_ref: str = "HEAD~1",
    pr_body: str = "",
    spec_file: str = "",
    repo_path: str = ".",
    use_llm: bool = False,
) -> str:
    """Run the full agent-verify pipeline and return a JSON verification report.

    Extracts intent from commits/PR/spec, computes AST-level diffs,
    runs structural and alignment verifiers, and produces a PASS/WARN/FAIL verdict.

    Args:
        diff_ref: Git ref to diff against (default: HEAD~1).
        pr_body: PR description text for intent extraction.
        spec_file: Path to a spec file (SPEC.md, RFC, etc.).
        repo_path: Path to the git repository root.
        use_llm: Whether to use LLM for spec-code alignment checking.

    Returns:
        JSON string with verdict, confidence, findings, and claim counts.
    """
    report = run_pipeline(
        diff_ref=diff_ref,
        pr_body=pr_body,
        spec_file=spec_file,
        repo_path=repo_path,
        use_llm=use_llm,
    )
    return json.dumps(_serialize(report), indent=2)


@mcp.tool()
def get_intent(
    pr_body: str = "",
    spec_file: str = "",
    commits: str = "",
    repo_path: str = ".",
) -> str:
    """Extract intent claims from PR description, spec file, and/or commit messages.

    Returns a list of atomic, testable claims about what the code change should do,
    each with a confidence level and intent type (feature, bugfix, refactor, etc.).

    Args:
        pr_body: PR description text.
        spec_file: Path to a spec file whose content will be read.
        commits: Comma-separated commit messages (e.g. "feat: add login,fix: handle null").
        repo_path: Path to the git repository (used if commits is empty to read git log).

    Returns:
        JSON string with extracted claims array and metadata.
    """
    from pathlib import Path

    context: dict[str, Any] = {}

    if pr_body:
        context["pr_body"] = pr_body

    if spec_file:
        spec_path = Path(spec_file)
        if spec_path.exists():
            context["spec_content"] = spec_path.read_text(encoding="utf-8")

    if commits:
        context["commits"] = [c.strip() for c in commits.split(",") if c.strip()]
    elif repo_path:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "log", "--format=%s", "HEAD~5..HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                msgs = [m.strip() for m in result.stdout.strip().split("\n") if m.strip()]
                context["commits"] = msgs
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    intent_graph = extract_intent(context)
    return json.dumps(_serialize(intent_graph), indent=2)


@mcp.tool()
def get_ast_diff(
    file_path: str,
    old_content: str = "",
    new_content: str = "",
) -> str:
    """Compute a structural AST-level diff for a single file.

    Compares old and new versions of a file using Tree-sitter to identify
    added, removed, and modified functions/classes/methods.

    Args:
        file_path: File path (used to detect language from extension).
        old_content: The original file content.
        new_content: The updated file content.

    Returns:
        JSON string with list of structural changes (added/removed/modified symbols).
    """
    language = detect_language(file_path)
    changes = compute_ast_diff(old_content, new_content, file_path, language)

    result = {
        "file_path": file_path,
        "language": language,
        "changes": _serialize(changes),
    }
    return json.dumps(result, indent=2)


def main() -> None:
    """Entry point for the agent-verify MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
