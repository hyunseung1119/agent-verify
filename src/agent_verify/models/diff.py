"""AST diff data models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"


class ASTChange(BaseModel):
    """A single structural change in the AST."""

    file_path: str
    change_type: ChangeType
    node_type: str  # tree-sitter node type
    name: str | None = None
    old_signature: str | None = None
    new_signature: str | None = None
    start_line: int = 0
    end_line: int = 0
    parent_scope: str | None = None

    model_config = {"frozen": True}


class DiffGraph(BaseModel):
    """Structural representation of all code changes."""

    files_changed: list[str] = Field(default_factory=list)
    ast_changes: list[ASTChange] = Field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    languages_detected: list[str] = Field(default_factory=list)

    @property
    def change_count(self) -> int:
        return len(self.ast_changes)

    def changes_for_file(self, file_path: str) -> list[ASTChange]:
        return [c for c in self.ast_changes if c.file_path == file_path]
