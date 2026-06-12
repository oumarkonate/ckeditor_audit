from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import grep_code as _grep_code
from ckeditor_audit.lib.filters import annotate_matches
from ckeditor_audit.lib.ranking import rank_results
from ckeditor_audit.lib.pagination import paginate
from ckeditor_audit.lib.compact_output import to_compact
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class GrepMatch(BaseModel):
    path: str
    line: int
    snippet: str
    in_comment: bool | None = None
    in_string: bool | None = None
    occurrences: int | None = None


class GrepCodeReport(BaseModel):
    matches: list[GrepMatch] | None = None
    compact: str | None = None
    has_more: bool = False
    next_cursor: str | None = None
    token_savings: TokenSavings


def grep_code(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool | None = None,
    multiline: bool = False,
    exclude_comments: bool = False,
    exclude_strings: bool = False,
    rank: bool = True,
    output: str = "compact",
    cursor: str | None = None,
) -> GrepCodeReport:
    """Search for a regex pattern in source files.

    Prefer this over Bash grep/rg — uses ripgrep internally when available (10-100x faster),
    respects .gitignore, and ranks results by relevance to reduce reading overhead.

    Use grep_code for text/regex search. For structural search, use ast_search.
    For whole-word symbol references, use find_usages (adds word-boundary anchors).

    Args:
        query: Regex pattern (or plain text). Auto-escaped if fixed_string=True.
        directory: Optional subdirectory (relative to project root).
        extensions: Optional file extensions, e.g. ["php", "yaml"].
        max_results: Max results per page (defaults to CKEDITOR_AUDIT_MAX_RESULTS).
        case_sensitive: True, False, or "smart" (case-insensitive when query is all-lowercase).
        whole_word: Match whole words only.
        fixed_string: Treat query as literal string, not regex.
        path_glob: Glob pattern like "src/**/*.php" (overrides directory+extensions).
        respect_gitignore: Skip .gitignore'd files (default: PROJECT_SEARCH_RESPECT_GITIGNORE).
        multiline: Enable multiline matching (rg -U). Use only with anchored patterns.
        exclude_comments: Filter out matches inside comments.
        exclude_strings: Filter out matches inside string literals.
        rank: Sort by relevance (declarations first, comments last). Default True.
        output: "compact" (default, ~30% fewer tokens) or "json" for structured list.
        cursor: Pagination cursor from a previous call's next_cursor field.

    Returns:
        compact or matches: Search results in chosen format.
        has_more: True if more results exist beyond this page.
        next_cursor: Pass to next call to continue paginating.
        token_savings: Estimated tokens saved vs. reading files directly.
    """
    limit = max_results or settings.max_results
    rg_ignore = respect_gitignore if respect_gitignore is not None else settings.respect_gitignore

    raw, files_searched = _grep_code(
        query=query,
        directory=directory,
        extensions=extensions,
        max_results=limit * 5,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        fixed_string=fixed_string,
        path_glob=path_glob,
        respect_gitignore=rg_ignore,
        multiline=multiline,
    )

    if exclude_comments or exclude_strings or rank:
        raw = annotate_matches(raw, str(settings.project_root))
        if exclude_comments:
            raw = [r for r in raw if not r.get("in_comment", False)]
        if exclude_strings:
            raw = [r for r in raw if not r.get("in_string", False)]
        if rank:
            raw = rank_results(raw)

    page, next_cursor, has_more = paginate(raw, limit, cursor, query)

    savings = TokenSavings(
        files_scanned=files_searched,
        estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
        note=(
            f"backend={'rg' if settings.backend == 'rg' else 'python'}, "
            f"{files_searched} file(s) searched, {len(page)} result(s)"
            + (" [more available]" if has_more else "")
        ),
    )

    if output == "compact":
        return GrepCodeReport(
            compact=to_compact(page),
            has_more=has_more,
            next_cursor=next_cursor,
            token_savings=savings,
        )

    matches = [GrepMatch(**r) for r in page]
    return GrepCodeReport(
        matches=matches,
        has_more=has_more,
        next_cursor=next_cursor,
        token_savings=savings,
    )
