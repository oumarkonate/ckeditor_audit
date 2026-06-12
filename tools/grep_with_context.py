from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import grep_with_context as _grep_with_context
from ckeditor_audit.lib.pagination import paginate
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class ContextMatch(BaseModel):
    path: str
    line: int
    snippet: str
    before: list[str]
    after: list[str]


class GrepContextReport(BaseModel):
    matches: list[ContextMatch]
    has_more: bool = False
    next_cursor: str | None = None
    token_savings: TokenSavings


def grep_with_context(
    query: str,
    context_lines: int = 3,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool | None = None,
    multiline: bool = False,
    cursor: str | None = None,
) -> GrepContextReport:
    """Search for a regex pattern and return surrounding lines for each match.

    Use this when you need to understand the code context around a match — e.g. to see
    the surrounding function body or imports. For just locating matches, grep_code is cheaper.

    Args:
        query: Regex pattern (or plain text) to search for.
        context_lines: Lines before/after each match (default 3, max 10).
        directory: Optional subdirectory (relative to project root).
        extensions: Optional file extensions, e.g. ["php", "yaml"].
        max_results: Max results per page (defaults to CKEDITOR_AUDIT_MAX_RESULTS).
        case_sensitive: True, False, or "smart".
        whole_word: Match whole words only.
        fixed_string: Treat query as literal string.
        path_glob: Glob pattern like "src/**/*.php".
        respect_gitignore: Skip .gitignore'd files.
        multiline: Enable multiline matching (rg -U). Use only with anchored patterns.
        cursor: Pagination cursor from previous call.

    Returns:
        matches: Each match with before/after context lines.
        has_more: True if more results exist.
        next_cursor: Pass to next call to paginate.
        token_savings: Estimated tokens saved.
    """
    limit = max_results or settings.max_results
    rg_ignore = respect_gitignore if respect_gitignore is not None else settings.respect_gitignore

    raw, files_searched = _grep_with_context(
        query=query,
        context_lines=context_lines,
        directory=directory,
        extensions=extensions,
        max_results=limit * 3,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        fixed_string=fixed_string,
        path_glob=path_glob,
        respect_gitignore=rg_ignore,
        multiline=multiline,
    )

    page, next_cursor, has_more = paginate(raw, limit, cursor, query)
    matches = [ContextMatch(**r) for r in page]

    return GrepContextReport(
        matches=matches,
        has_more=has_more,
        next_cursor=next_cursor,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=(
                f"searched {files_searched} file(s), {len(matches)} match(es) "
                f"with {context_lines} context line(s)"
                + (" [more available]" if has_more else "")
            ),
        ),
    )
