"""AST-level diff analysis using Tree-sitter."""

from __future__ import annotations

import re
from pathlib import Path

from agent_verify.models.diff import ASTChange, ChangeType, DiffGraph

# Language detection from file extension
LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
}

# Tree-sitter node types that represent definitions per language
DEFINITION_TYPES: dict[str, list[str]] = {
    "python": [
        "function_definition",
        "class_definition",
        "decorated_definition",
    ],
    "typescript": [
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
    ],
    "javascript": [
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
    ],
    "go": [
        "function_declaration",
        "method_declaration",
        "type_declaration",
    ],
    "rust": [
        "function_item",
        "impl_item",
        "struct_item",
        "enum_item",
        "trait_item",
    ],
}


def detect_language(file_path: str) -> str | None:
    """Detect language from file extension."""
    suffix = Path(file_path).suffix.lower()
    return LANG_MAP.get(suffix)


def compute_ast_diff(
    old_content: str,
    new_content: str,
    file_path: str,
    language: str | None = None,
) -> list[ASTChange]:
    """Compare two versions of a file at the AST level using Tree-sitter."""
    if language is None:
        language = detect_language(file_path)
    if language is None:
        return []

    try:
        import tree_sitter_languages as tsl
        from tree_sitter import Parser

        lang_obj = tsl.get_language(language)
        parser = Parser()
        try:
            parser.language = lang_obj
        except TypeError:
            parser = Parser(lang_obj)

        old_tree = parser.parse(bytes(old_content, "utf8"))
        new_tree = parser.parse(bytes(new_content, "utf8"))

        old_defs = _extract_definitions(old_tree.root_node, language)
        new_defs = _extract_definitions(new_tree.root_node, language)

        return _compare_definitions(old_defs, new_defs, file_path)

    except (ImportError, TypeError, Exception):
        return _fallback_diff(old_content, new_content, file_path)


def _extract_definitions(root_node, language: str) -> dict[str, dict]:
    """Extract function/class definitions from AST."""
    defs: dict[str, dict] = {}
    target_types = DEFINITION_TYPES.get(language, [])

    def walk(node, parent_name: str = ""):
        if node.type in target_types:
            name = _get_node_name(node, language)
            if name:
                signature = _get_signature(node)
                defs[name] = {
                    "type": node.type,
                    "name": name,
                    "signature": signature,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "parent": parent_name,
                    "text_hash": hash(node.text),
                }
                for child in node.children:
                    walk(child, name)
                return

        for child in node.children:
            walk(child, parent_name)

    walk(root_node)
    return defs


def _get_node_name(node, language: str) -> str | None:
    """Extract the name of a definition node."""
    for child in node.children:
        if child.type in ("identifier", "property_identifier", "type_identifier"):
            return child.text.decode("utf8")
        if child.type == "name":
            return child.text.decode("utf8")
    return None


def _get_signature(node) -> str:
    """Extract function/class signature (first line)."""
    text = node.text.decode("utf8", errors="replace")
    first_line = text.split("\n")[0]
    return first_line[:200]


def _compare_definitions(
    old_defs: dict[str, dict],
    new_defs: dict[str, dict],
    file_path: str,
) -> list[ASTChange]:
    """Compare old and new definitions to find changes."""
    changes: list[ASTChange] = []
    all_names = set(old_defs.keys()) | set(new_defs.keys())

    for name in all_names:
        old = old_defs.get(name)
        new = new_defs.get(name)

        if old is None and new is not None:
            changes.append(
                ASTChange(
                    file_path=file_path,
                    change_type=ChangeType.ADDED,
                    node_type=new["type"],
                    name=name,
                    new_signature=new["signature"],
                    start_line=new["start_line"],
                    end_line=new["end_line"],
                    parent_scope=new.get("parent"),
                )
            )
        elif old is not None and new is None:
            changes.append(
                ASTChange(
                    file_path=file_path,
                    change_type=ChangeType.REMOVED,
                    node_type=old["type"],
                    name=name,
                    old_signature=old["signature"],
                    start_line=old["start_line"],
                    end_line=old["end_line"],
                    parent_scope=old.get("parent"),
                )
            )
        elif old is not None and new is not None and old["text_hash"] != new["text_hash"]:
            changes.append(
                ASTChange(
                    file_path=file_path,
                    change_type=ChangeType.MODIFIED,
                    node_type=new["type"],
                    name=name,
                    old_signature=old["signature"],
                    new_signature=new["signature"],
                    start_line=new["start_line"],
                    end_line=new["end_line"],
                    parent_scope=new.get("parent"),
                )
            )

    return changes


def _fallback_diff(old_content: str, new_content: str, file_path: str) -> list[ASTChange]:
    """Fallback when tree-sitter is not available: regex-based extraction."""
    changes: list[ASTChange] = []
    language = detect_language(file_path) or "unknown"

    old_funcs = _regex_extract_functions(old_content, language)
    new_funcs = _regex_extract_functions(new_content, language)

    for name in set(new_funcs) - set(old_funcs):
        changes.append(
            ASTChange(
                file_path=file_path,
                change_type=ChangeType.ADDED,
                node_type="function",
                name=name,
            )
        )

    for name in set(old_funcs) - set(new_funcs):
        changes.append(
            ASTChange(
                file_path=file_path,
                change_type=ChangeType.REMOVED,
                node_type="function",
                name=name,
            )
        )

    return changes


_FUNC_PATTERNS: dict[str, re.Pattern] = {
    "python": re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", re.MULTILINE),
    "typescript": re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|(\w+)\s*[=:]\s*(?:async\s+)?\(",
        re.MULTILINE,
    ),
    "javascript": re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|(\w+)\s*[=:]\s*(?:async\s+)?\(",
        re.MULTILINE,
    ),
    "go": re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", re.MULTILINE),
    "rust": re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE),
}


def _regex_extract_functions(content: str, language: str) -> set[str]:
    """Extract function names using regex (fallback)."""
    pattern = _FUNC_PATTERNS.get(language)
    if pattern is None:
        return set()
    matches = pattern.findall(content)
    names: set[str] = set()
    for match in matches:
        if isinstance(match, tuple):
            name = next((m for m in match if m), None)
        else:
            name = match
        if name:
            names.add(name)
    return names


def build_diff_graph(
    file_diffs: list[dict[str, str]],
) -> DiffGraph:
    """
    Build a DiffGraph from a list of file diffs.

    Each dict in file_diffs should have:
      - file_path: str
      - old_content: str
      - new_content: str
    """
    all_changes: list[ASTChange] = []
    files: list[str] = []
    languages: set[str] = set()
    total_added = 0
    total_removed = 0

    for fd in file_diffs:
        file_path = fd["file_path"]
        old = fd.get("old_content", "")
        new = fd.get("new_content", "")
        files.append(file_path)

        lang = detect_language(file_path)
        if lang:
            languages.add(lang)

        changes = compute_ast_diff(old, new, file_path, lang)
        all_changes.extend(changes)

        old_lines = old.count("\n")
        new_lines = new.count("\n")
        if new_lines > old_lines:
            total_added += new_lines - old_lines
        else:
            total_removed += old_lines - new_lines

    return DiffGraph(
        files_changed=files,
        ast_changes=all_changes,
        lines_added=total_added,
        lines_removed=total_removed,
        languages_detected=sorted(languages),
    )
