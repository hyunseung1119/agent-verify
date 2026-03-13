"""Tests for AST diff analysis."""

from __future__ import annotations

import pytest

from agent_verify.analyzers.ast_differ import (
    LANG_MAP,
    _fallback_diff,
    _regex_extract_functions,
    build_diff_graph,
    compute_ast_diff,
    detect_language,
)
from agent_verify.models.diff import ChangeType


class TestDetectLanguage:
    def test_python(self):
        assert detect_language("main.py") == "python"

    def test_typescript(self):
        assert detect_language("app.ts") == "typescript"

    def test_tsx(self):
        assert detect_language("Component.tsx") == "tsx"

    def test_javascript(self):
        assert detect_language("index.js") == "javascript"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_rust(self):
        assert detect_language("lib.rs") == "rust"

    def test_unknown(self):
        assert detect_language("file.txt") is None
        assert detect_language("Makefile") is None

    def test_nested_path(self):
        assert detect_language("src/components/Button.tsx") == "tsx"

    def test_case_insensitive(self):
        assert detect_language("file.PY") == "python"


class TestRegexExtractFunctions:
    def test_python_functions(self):
        code = """
def hello():
    pass

async def fetch_data():
    pass

class MyClass:
    def method(self):
        pass
"""
        funcs = _regex_extract_functions(code, "python")
        assert "hello" in funcs
        assert "fetch_data" in funcs
        assert "method" in funcs

    def test_go_functions(self):
        code = """
func main() {
}

func (s *Server) HandleRequest(w http.ResponseWriter, r *http.Request) {
}

func helper() string {
}
"""
        funcs = _regex_extract_functions(code, "go")
        assert "main" in funcs
        assert "HandleRequest" in funcs
        assert "helper" in funcs

    def test_rust_functions(self):
        code = """
fn main() {
}

pub fn process(data: &[u8]) -> Result<(), Error> {
}

pub async fn fetch() -> String {
}
"""
        funcs = _regex_extract_functions(code, "rust")
        assert "main" in funcs
        assert "process" in funcs
        assert "fetch" in funcs

    def test_unknown_language(self):
        funcs = _regex_extract_functions("some content", "unknown")
        assert funcs == set()

    def test_empty_content(self):
        funcs = _regex_extract_functions("", "python")
        assert funcs == set()


class TestFallbackDiff:
    def test_added_function(self):
        old = "def existing():\n    pass\n"
        new = "def existing():\n    pass\n\ndef new_func():\n    pass\n"
        changes = _fallback_diff(old, new, "test.py")
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].name == "new_func"

    def test_removed_function(self):
        old = "def old_func():\n    pass\n\ndef keep():\n    pass\n"
        new = "def keep():\n    pass\n"
        changes = _fallback_diff(old, new, "test.py")
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].name == "old_func"

    def test_no_changes(self):
        code = "def same():\n    pass\n"
        changes = _fallback_diff(code, code, "test.py")
        assert changes == []


class TestBuildDiffGraph:
    def test_single_file(self):
        diffs = [
            {
                "file_path": "app.py",
                "old_content": "def old():\n    pass\n",
                "new_content": "def old():\n    return 1\n\ndef new_func():\n    pass\n",
            }
        ]
        graph = build_diff_graph(diffs)
        assert "app.py" in graph.files_changed
        assert "python" in graph.languages_detected
        assert graph.change_count > 0

    def test_multiple_files(self):
        diffs = [
            {
                "file_path": "a.py",
                "old_content": "",
                "new_content": "def hello():\n    pass\n",
            },
            {
                "file_path": "b.go",
                "old_content": "",
                "new_content": "func main() {\n}\n",
            },
        ]
        graph = build_diff_graph(diffs)
        assert len(graph.files_changed) == 2
        assert "python" in graph.languages_detected
        assert "go" in graph.languages_detected

    def test_empty_diffs(self):
        graph = build_diff_graph([])
        assert graph.files_changed == []
        assert graph.change_count == 0

    def test_lines_added_tracked(self):
        diffs = [
            {
                "file_path": "new.py",
                "old_content": "",
                "new_content": "line1\nline2\nline3\n",
            }
        ]
        graph = build_diff_graph(diffs)
        assert graph.lines_added > 0

    def test_changes_for_file(self):
        diffs = [
            {
                "file_path": "a.py",
                "old_content": "",
                "new_content": "def hello():\n    pass\n",
            },
            {
                "file_path": "b.py",
                "old_content": "",
                "new_content": "def world():\n    pass\n",
            },
        ]
        graph = build_diff_graph(diffs)
        a_changes = graph.changes_for_file("a.py")
        b_changes = graph.changes_for_file("b.py")
        assert all(c.file_path == "a.py" for c in a_changes)
        assert all(c.file_path == "b.py" for c in b_changes)
