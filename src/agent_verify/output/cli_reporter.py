"""Rich terminal output for verification reports."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent_verify.models.report import FindingSeverity, Verdict, VerifyReport


VERDICT_STYLES = {
    Verdict.PASS: ("bold green", "PASS"),
    Verdict.WARN: ("bold yellow", "WARN"),
    Verdict.FAIL: ("bold red", "FAIL"),
    Verdict.INCONCLUSIVE: ("bold dim", "???"),
}

SEVERITY_STYLES = {
    FindingSeverity.CRITICAL: "bold red",
    FindingSeverity.HIGH: "red",
    FindingSeverity.MEDIUM: "yellow",
    FindingSeverity.LOW: "dim",
    FindingSeverity.INFO: "blue",
}


def print_report(report: VerifyReport, console: Console | None = None) -> None:
    """Print a verification report to the terminal."""
    if console is None:
        console = Console()

    style, label = VERDICT_STYLES[report.verdict]

    # Header
    console.print()
    console.print(
        Panel(
            f"[{style}]{label}[/] | "
            f"Confidence: {report.confidence_score:.0%} | "
            f"Claims: {report.claims_verified}/{report.claims_total} verified | "
            f"Findings: {len(report.findings)}",
            title="[bold]agent-verify[/bold]",
            border_style=style.replace("bold ", ""),
        )
    )

    # Findings table
    if report.findings:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Severity", width=10)
        table.add_column("Category", width=20)
        table.add_column("Title")
        table.add_column("File", width=25)

        for finding in sorted(report.findings, key=lambda f: list(FindingSeverity).index(f.severity)):
            sev_style = SEVERITY_STYLES[finding.severity]
            table.add_row(
                f"[{sev_style}]{finding.severity.value.upper()}[/]",
                finding.category,
                finding.title[:60],
                (finding.file_path or "")[:25],
            )

        console.print(table)

    # Suggestions for critical/high findings
    critical_high = [
        f for f in report.findings
        if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH) and f.suggestion
    ]
    if critical_high:
        console.print("\n[bold]Suggestions:[/bold]")
        for f in critical_high:
            console.print(f"  - {f.title}: {f.suggestion}")

    console.print(f"\n[dim]Pipeline v{report.pipeline_version} | {report.execution_time_seconds:.1f}s[/dim]")
    console.print()
