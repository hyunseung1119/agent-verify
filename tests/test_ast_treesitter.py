"""Tests for tree-sitter AST diff (real parsing, not fallback)."""

from __future__ import annotations

from agent_verify.analyzers.ast_differ import (
    _extract_definitions,
    _get_node_name,
    _get_signature,
    compute_ast_diff,
)
from agent_verify.models.diff import ChangeType


def _parse(code: str, language: str = "python"):
    """Parse code with tree-sitter and return root node."""
    import warnings

    import tree_sitter_languages as tsl
    from tree_sitter import Parser

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        lang = tsl.get_language(language)
    parser = Parser()
    parser.set_language(lang)
    return parser.parse(bytes(code, "utf8")).root_node


class TestTreeSitterASTDiff:
    def test_detect_added_function(self):
        old = "def existing():\n    pass\n"
        new = "def existing():\n    pass\n\ndef new_func(x):\n    return x * 2\n"
        changes = compute_ast_diff(old, new, "test.py", "python")
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].name == "new_func"
        assert added[0].node_type == "function_definition"
        assert added[0].start_line > 0

    def test_detect_removed_function(self):
        old = "def remove_me():\n    pass\n\ndef keep():\n    pass\n"
        new = "def keep():\n    pass\n"
        changes = compute_ast_diff(old, new, "test.py", "python")
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].name == "remove_me"

    def test_detect_modified_function(self):
        old = "def calc(x):\n    return x\n"
        new = "def calc(x):\n    return x * 2\n"
        changes = compute_ast_diff(old, new, "test.py", "python")
        modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
        assert len(modified) == 1
        assert modified[0].name == "calc"

    def test_no_changes(self):
        code = "def same():\n    pass\n"
        changes = compute_ast_diff(code, code, "test.py", "python")
        assert changes == []

    def test_class_detection(self):
        old = ""
        new = "class MyClass:\n    def method(self):\n        pass\n"
        changes = compute_ast_diff(old, new, "test.py", "python")
        added_names = {c.name for c in changes if c.change_type == ChangeType.ADDED}
        assert "MyClass" in added_names

    def test_signature_captured(self):
        old = ""
        new = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
        changes = compute_ast_diff(old, new, "test.py", "python")
        assert len(changes) >= 1
        assert "greet" in (changes[0].new_signature or "")

    def test_unknown_language_returns_empty(self):
        changes = compute_ast_diff("content", "content", "file.xyz")
        assert changes == []

    def test_auto_detect_language(self):
        old = ""
        new = "def auto():\n    pass\n"
        changes = compute_ast_diff(old, new, "module.py")
        assert len(changes) >= 1


class TestExtractDefinitions:
    def test_python_functions(self):
        root = _parse("def foo():\n    pass\n\ndef bar(x):\n    return x\n")
        defs = _extract_definitions(root, "python")
        assert "foo" in defs
        assert "bar" in defs

    def test_python_class(self):
        root = _parse("class Dog:\n    def bark(self):\n        pass\n")
        defs = _extract_definitions(root, "python")
        assert "Dog" in defs

    def test_empty_code(self):
        root = _parse("")
        defs = _extract_definitions(root, "python")
        assert defs == {}


class TestGetNodeName:
    def test_function_name(self):
        root = _parse("def my_func():\n    pass\n")
        func_node = root.children[0]
        name = _get_node_name(func_node, "python")
        assert name == "my_func"


class TestGetSignature:
    def test_captures_first_line(self):
        root = _parse("def long_func(a, b, c):\n    x = 1\n    return x\n")
        func_node = root.children[0]
        sig = _get_signature(func_node)
        assert "long_func" in sig
        assert "return" not in sig
