# agent-verify

**AI가 생성한 코드가 "의도대로 동작하는지" 자동 검증하는 엔진**

AI code verification engine — validates whether AI-generated code actually does what was intended.

> "SWE-bench를 통과한 PR의 ~50%가 실제 메인테이너에 의해 머지되지 않았다" — METR Research, 2025
>
> "~50% of SWE-bench-passing PRs wouldn't be merged by maintainers" — METR Research, 2025

---

## 왜 만들었는가 / Why?

AI 코딩 에이전트는 **실행되는 코드**를 만들지만, **의도대로 동작하는 코드**를 보장하지 않습니다.
기존 리뷰 도구(linter, formatter, type checker)는 **스타일과 문법**만 확인합니다.
**"이 코드가 PR에 적힌 목적을 실제로 달성했는가?"** 를 검증하는 도구는 없었습니다.

AI coding agents generate code that *runs* but doesn't always *work correctly*.
Current review tools check style and syntax — not whether the code fulfills its stated intent.
agent-verify bridges this gap: **"Does this code actually do what the PR said it would?"**

```
The Gap (2026):
  AI generates code  ──→  Linter says OK  ──→  Tests pass  ──→  But does it do the RIGHT thing?
                                                                  ↑ agent-verify fills this gap
```

---

## 동작 원리 / How It Works

```
Intent Sources              Verification Pipeline              Output
┌─────────────┐            ┌──────────────────────┐          ┌────────────┐
│ PR Body      │───┐       │ 1. Intent Extraction │          │ PASS/WARN/ │
│ Commit Msgs  │───┤──────▶│ 2. AST Diff Analysis │─────────▶│ FAIL +     │
│ Spec Files   │───┘       │ 3. Structural Verify │          │ Findings   │
└─────────────┘            │ 4. Alignment Check   │          └────────────┘
                           └──────────────────────┘
```

| 단계 / Stage | 설명 / Description |
|---|---|
| **1. Intent Extraction** | PR 설명, conventional commits, spec 파일에서 검증 가능한 claim 추출 / Parses PR descriptions, commits, and spec files into atomic, testable claims |
| **2. AST Diff Analysis** | Tree-sitter 기반 구조적 diff (라인 diff가 아닌 AST 수준) — 9개 언어 지원 / Tree-sitter structural diff (not line-based) across 9 languages |
| **3. Structural Verify** | 패턴 매칭: feature claim에 코드 추가가 있는지, bugfix에 기존 코드 수정이 있는지, scope creep 감지 / Pattern matching: features have additions, bugfixes modify existing code, scope creep detection |
| **4. Alignment Check** | 휴리스틱 또는 LLM 기반으로 claim이 실제 코드 변경에 매핑되는지 검증 / Heuristic or LLM-based verification that claims trace to actual code changes |

---

## 설치 / Installation

```bash
pip install agent-verify

# LLM 기반 alignment 사용 시 (선택)
pip install agent-verify[llm]

# MCP Server로 Claude Code 연동 시
pip install agent-verify[mcp]
```

---

## 빠른 시작 / Quick Start

```bash
# 마지막 커밋 검증
agent-verify check

# 특정 ref + PR 컨텍스트로 검증
agent-verify check --diff HEAD~3 --pr-body "## What
- Add user authentication
- Fix login bug"

# Spec 파일 기반 검증
agent-verify check --spec SPEC.md

# CI용 JSON 출력
agent-verify check --json-output --fail-on-warn

# LLM 기반 alignment (ANTHROPIC_API_KEY 필요)
agent-verify check --llm
```

### 출력 예시 / Example Output

```
╭──────────── agent-verify ────────────╮
│ PASS | Confidence: 92% | Claims: 3/3 verified | Findings: 1 │
╰──────────────────────────────────────╯
┌──────────┬──────────────────────┬────────────────────────────────┬──────────┐
│ Severity │ Category             │ Title                          │ File     │
├──────────┼──────────────────────┼────────────────────────────────┼──────────┤
│ LOW      │ scope_creep          │ Changes broader than intent    │ utils.py │
└──────────┴──────────────────────┴────────────────────────────────┴──────────┘
```

---

## CLI 명령어 / Commands

| 명령어 / Command | 설명 / Description |
|---|---|
| `agent-verify check` | 검증 파이프라인 실행 / Run verification pipeline |
| `agent-verify add-claim` | 수동으로 검증 claim 추가 / Manually add a verification claim |
| `agent-verify info` | 설정 및 기능 확인 / Show configuration and capabilities |

### `check` 옵션 / Options

| Flag | Default | 설명 / Description |
|---|---|---|
| `--diff` | `HEAD~1` | diff 대상 Git ref / Git ref to diff against |
| `--pr-body` | | PR 설명 텍스트 / PR description text |
| `--pr-body-file` | | PR 설명 파일 경로 / File containing PR description |
| `--spec` | auto-detect | spec 파일 경로 / Path to spec file |
| `--repo` | `.` | Git 저장소 경로 / Path to git repository |
| `--llm/--no-llm` | `--no-llm` | LLM 사용 여부 / Use LLM for alignment |
| `--json-output` | | JSON 출력 / Output as JSON |
| `--fail-on-warn` | | WARN에도 exit code 1 / Exit code 1 on WARN |

---

## GitHub Action

```yaml
# .github/workflows/verify.yml
name: Verify AI Code
on: [pull_request]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: hyunseung1119/agent-verify@v0.2
        with:
          fail_on_warn: true
```

---

## MCP Server (Claude Code 연동)

```bash
# MCP 서버 시작
agent-verify-mcp

# Claude Code settings.json에 추가:
{
  "mcpServers": {
    "agent-verify": {
      "command": "agent-verify-mcp",
      "args": []
    }
  }
}
```

사용 가능한 MCP 도구:
- `verify_changes` — 전체 검증 파이프라인 실행
- `get_intent` — PR/커밋/spec에서 intent 추출
- `get_ast_diff` — 파일의 구조적 diff 분석

---

## 지원 언어 / Supported Languages

Python, TypeScript, TSX, JavaScript, JSX, Go, Rust, Java, Ruby

---

## 판정 기준 / Verdicts

| Verdict | 의미 / Meaning |
|---|---|
| **PASS** | 모든 claim 검증됨, 높은 신뢰도 / All claims verified, high confidence |
| **WARN** | 일부 우려 사항, 수동 리뷰 권장 / Some concerns, manual review recommended |
| **FAIL** | 심각한 문제 발견 또는 claim 추적 불가 / Critical issues or claims not traceable |
| **INCONCLUSIVE** | 검증을 위한 정보 부족 / Not enough information to verify |

---

## 프로젝트 수치 / Project Metrics

| Metric | Value |
|---|---|
| Tests | 116 passed |
| Coverage | 86% |
| Languages | 9 |
| Pipeline stages | 4 |
| Tree-sitter | real AST parsing |
| CI | GitHub Actions (Python 3.11/3.12) |

---

## 개발 / Development

```bash
git clone https://github.com/hyunseung1119/agent-verify.git
cd agent-verify
pip install -e ".[dev]"
pytest
```

---

## 아키텍처 / Architecture

```
src/agent_verify/
├── models/              # Pydantic 데이터 모델
│   ├── intent.py        # IntentClaim, IntentGraph, Confidence
│   ├── diff.py          # ASTChange, DiffGraph, ChangeType
│   └── report.py        # VerifyReport, Finding, Verdict
├── ingest/
│   └── intent_extractor.py  # CommitMessage, PRDescription, SpecFile 소스
├── analyzers/
│   └── ast_differ.py    # Tree-sitter AST diff + regex fallback
├── verifiers/
│   ├── structural.py    # 구조적 패턴 검증
│   └── alignment.py     # spec-code alignment (heuristic/LLM)
├── output/
│   └── cli_reporter.py  # Rich 터미널 출력
├── pipeline.py          # 메인 오케스트레이터
├── cli.py               # Click CLI
└── mcp_server.py        # MCP Server (Claude Code 연동)
```

---

## 로드맵 / Roadmap

- [x] v0.1 — Core pipeline (intent → AST diff → verify → verdict)
- [x] v0.2 — Tree-sitter fix, CI, 86% coverage
- [x] v0.3 — MCP Server, GitHub Action
- [ ] v0.4 — Mutation testing integration
- [ ] v0.5 — Multi-repo support, caching
- [ ] v1.0 — PyPI publish, stable API

---

## 라이선스 / License

MIT
