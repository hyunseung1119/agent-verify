# agent-verify

AI code verification engine that validates whether AI-generated code actually does what was intended.

> "~50% of SWE-bench-passing PRs wouldn't be merged by maintainers" — METR Research, 2025

## Problem

AI coding agents generate code that *runs* but doesn't always *work correctly*. Current review tools check style and syntax, not whether the code fulfills its stated intent. agent-verify bridges this gap.

## How It Works

```
Intent Sources              Verification Pipeline              Output
┌─────────────┐            ┌──────────────────────┐          ┌────────────┐
│ PR Body      │───┐       │ 1. Intent Extraction │          │ PASS/WARN/ │
│ Commit Msgs  │───┤──────▶│ 2. AST Diff Analysis │─────────▶│ FAIL +     │
│ Spec Files   │───┘       │ 3. Structural Verify │          │ Findings   │
└─────────────┘            │ 4. Alignment Check   │          └────────────┘
                           └──────────────────────┘
```

1. **Intent Extraction** — Parses PR descriptions, conventional commits, and spec files into atomic, testable claims
2. **AST Diff Analysis** — Tree-sitter structural diff (not line-based) across 9 languages
3. **Structural Verification** — Checks patterns: features have additions, bugfixes modify existing code, scope creep detection
4. **Spec-Code Alignment** — Heuristic or LLM-based verification that claims trace to actual code changes

## Installation

```bash
pip install agent-verify

# With LLM-based alignment (optional)
pip install agent-verify[llm]
```

## Quick Start

```bash
# Verify the last commit
agent-verify check

# Verify against a specific ref with PR context
agent-verify check --diff HEAD~3 --pr-body "## What\n- Add user auth\n- Fix login bug"

# With a spec file
agent-verify check --spec SPEC.md

# JSON output for CI
agent-verify check --json-output --fail-on-warn

# LLM-powered alignment (requires ANTHROPIC_API_KEY)
agent-verify check --llm
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `agent-verify check` | Run verification pipeline |
| `agent-verify add-claim` | Manually add a verification claim |
| `agent-verify info` | Show configuration and capabilities |

### `check` Options

| Flag | Default | Description |
|------|---------|-------------|
| `--diff` | `HEAD~1` | Git ref to diff against |
| `--pr-body` | | PR description text |
| `--pr-body-file` | | File containing PR description |
| `--spec` | auto-detect | Path to spec file |
| `--repo` | `.` | Path to git repository |
| `--llm/--no-llm` | `--no-llm` | Use LLM for alignment |
| `--json-output` | | Output as JSON |
| `--fail-on-warn` | | Exit code 1 on WARN too |

## Supported Languages

Python, TypeScript, TSX, JavaScript, JSX, Go, Rust, Java, Ruby

## Verdicts

| Verdict | Meaning |
|---------|---------|
| **PASS** | All claims verified, high confidence |
| **WARN** | Some concerns, manual review recommended |
| **FAIL** | Critical issues found or claims not traceable |
| **INCONCLUSIVE** | Not enough information to verify |

## Development

```bash
git clone https://github.com/hyunseung1119/agent-verify.git
cd agent-verify
pip install -e ".[dev]"
pytest
```

## License

MIT
