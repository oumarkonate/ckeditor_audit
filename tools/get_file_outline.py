from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class OutlineEntry(BaseModel):
    kind: str
    name: str
    line: int
    visibility: str | None = None


class GetFileOutlineReport(BaseModel):
    results: list[OutlineEntry]
    token_savings: TokenSavings


def get_file_outline(path: str) -> GetFileOutlineReport:
    """List all classes, methods, and functions in a file with their line numbers.

    Uses ast-grep when available for accurate PHP/JS/TS parsing (handles generics,
    decorators, arrow functions, multi-line declarations). Falls back to regex.

    Use this before read_file to understand a file's structure — decide which method
    to read without loading the whole file.

    Args:
        path: Relative path from project root (e.g. "src/Domain/Services/ContentService.php").

    Returns:
        results: Declarations ordered by line, with kind, name, line, and visibility.
        token_savings: Estimated tokens saved vs. reading the full file.
    """
    if settings.ast_grep_available:
        from ckeditor_audit.lib.backends.astgrep import get_file_outline as _ag_outline
        raw = _ag_outline(path, settings.project_root)
    else:
        from ckeditor_audit.lib.searcher import get_file_outline as _get_file_outline
        raw = _get_file_outline(path)

    results = [OutlineEntry(**entry) for entry in raw]
    backend = "ast-grep" if settings.ast_grep_available else "regex"
    return GetFileOutlineReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=1,
            estimated_tokens_saved=_TOKENS_PER_FILE,
            note=f"backend={backend}, parsed {path}, {len(results)} declaration(s)",
        ),
    )
