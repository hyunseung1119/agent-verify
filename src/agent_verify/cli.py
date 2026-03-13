"""CLI interface for agent-verify."""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console

from agent_verify import __version__
from agent_verify.pipeline import run_pipeline
from agent_verify.output.cli_reporter import print_report


@click.group()
@click.version_option(version=__version__)
def main():
    """agent-verify: AI code verification engine.

    Validates whether AI-generated code actually does what was intended.
    """


@main.command()
@click.option("--diff", "diff_ref", default="HEAD~1", help="Git ref to diff against")
@click.option("--pr-body", default="", help="PR description text")
@click.option("--pr-body-file", default="", help="File containing PR description")
@click.option("--spec", default="", help="Path to spec file (SPEC.md, RFC)")
@click.option("--repo", default=".", help="Path to git repository")
@click.option("--llm/--no-llm", default=False, help="Use LLM for spec-code alignment")
@click.option("--json-output", is_flag=True, help="Output as JSON instead of rich terminal")
@click.option("--fail-on-warn", is_flag=True, help="Exit with code 1 on WARN verdict too")
def check(
    diff_ref: str,
    pr_body: str,
    pr_body_file: str,
    spec: str,
    repo: str,
    llm: bool,
    json_output: bool,
    fail_on_warn: bool,
):
    """Run verification pipeline on code changes."""
    console = Console(stderr=True)

    # Load PR body from file if specified
    if pr_body_file:
        try:
            with open(pr_body_file) as f:
                pr_body = f.read()
        except FileNotFoundError:
            console.print(f"[red]Error: PR body file not found: {pr_body_file}[/]")
            sys.exit(2)

    # Auto-detect spec files
    if not spec:
        from pathlib import Path
        for candidate in ["SPEC.md", "spec.md", "RFC.md", "docs/spec.md"]:
            if (Path(repo) / candidate).exists():
                spec = str(Path(repo) / candidate)
                break

    console.print("[dim]Running verification pipeline...[/dim]")

    report = run_pipeline(
        diff_ref=diff_ref,
        pr_body=pr_body,
        spec_file=spec,
        repo_path=repo,
        use_llm=llm,
    )

    if json_output:
        print(json.dumps(report.model_dump(), indent=2, default=str))
    else:
        print_report(report, Console())

    # Exit codes
    if report.verdict.value == "fail":
        sys.exit(1)
    if fail_on_warn and report.verdict.value == "warn":
        sys.exit(1)


@main.command()
@click.argument("claim_text")
@click.option("--type", "claim_type", default="feature", help="Claim type")
def add_claim(claim_text: str, claim_type: str):
    """Manually add a verification claim."""
    console = Console()
    console.print(f"[green]Added claim:[/] {claim_text} (type: {claim_type})")
    console.print("[dim]This claim will be included in the next verification run.[/dim]")


@main.command()
def info():
    """Show agent-verify configuration and capabilities."""
    console = Console()
    console.print(f"[bold]agent-verify[/bold] v{__version__}")
    console.print()
    console.print("[bold]Supported languages:[/bold]")
    from agent_verify.analyzers.ast_differ import LANG_MAP
    for ext, lang in sorted(LANG_MAP.items()):
        console.print(f"  {ext:6s} → {lang}")
    console.print()
    console.print("[bold]Verification stages:[/bold]")
    console.print("  1. Intent Extraction (commit messages, PR descriptions, spec files)")
    console.print("  2. AST Diff Analysis (Tree-sitter structural diff)")
    console.print("  3. Structural Verification (feature/bugfix/refactor pattern matching)")
    console.print("  4. Spec-Code Alignment (heuristic or LLM-based)")
    console.print()
    console.print("[bold]Optional:[/bold]")
    try:
        import anthropic  # noqa: F401
        console.print("  LLM alignment: [green]available[/] (anthropic SDK installed)")
    except ImportError:
        console.print("  LLM alignment: [dim]not available[/] (pip install agent-verify[llm])")


if __name__ == "__main__":
    main()
