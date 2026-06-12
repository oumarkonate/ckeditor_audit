from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_method as _find_method
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class MethodLocation(BaseModel):
    path: str
    line: int
    kind: str
    class_name: str | None
    visibility: str | None


class FindMethodReport(BaseModel):
    results: list[MethodLocation]
    token_savings: TokenSavings


def find_method(
    method_name: str,
    class_name: str | None = None,
    directory: str | None = None,
) -> FindMethodReport:
    """Locate method or function declarations by name (PHP and JS/TS).

    Uses ast-grep when available for accurate detection of methods in complex
    class hierarchies. Falls back to regex-based detection.

    Prefer find_definition when unsure of the symbol kind — it tries class, method,
    and function lookups in one call.

    Args:
        method_name: Method or function name (case-insensitive).
        class_name: Optional PHP class name to narrow the search to a specific class.
        directory: Optional subdirectory (relative to project root).

    Returns:
        results: Declarations with path, line, kind (method/function), class name, visibility.
        token_savings: Estimated tokens saved vs. reading files directly.
    """
    raw, files_searched = _find_method(method_name, class_name, directory)
    results = [MethodLocation(**r) for r in raw]
    backend = "ast-grep" if settings.ast_grep_available else "regex"
    return FindMethodReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=(
                f"backend={backend}, searched {files_searched} file(s), "
                f"found {len(results)} declaration(s) of '{method_name}'"
            ),
        ),
    )
