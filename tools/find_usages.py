from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_usages as _find_usages
from ckeditor_audit.lib.pagination import paginate
from ckeditor_audit.lib.compact_output import to_compact
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class UsageMatch(BaseModel):
    path: str
    line: int
    snippet: str
    in_comment: bool | None = None
    in_string: bool | None = None


class FindUsagesReport(BaseModel):
    matches: list[UsageMatch] | None = None
    compact: str | None = None
    has_more: bool = False
    next_cursor: str | None = None
    token_savings: TokenSavings


def find_usages(
    symbol: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
    exclude_comments: bool = False,
    exclude_strings: bool = False,
    rank: bool = True,
    output: str = "compact",
    cursor: str | None = None,
) -> FindUsagesReport:
    """Find all references to a symbol across the project using whole-word match.

    More precise than grep_code for symbol lookups — avoids matching substrings
    (e.g. searching 'User' won't match 'UserRepository' or 'isUser').
    Results are ranked: declarations appear before usages, which appear before comments.

    Tip: use exclude_comments=True to see only actual code usages.

    Args:
        symbol: Symbol name to search for (class, method, variable, constant, etc.).
        directory: Optional subdirectory to restrict the search.
        extensions: Optional file extensions to search, e.g. ["php", "ts"].
        exclude_comments: Filter out matches inside comments.
        exclude_strings: Filter out matches inside string literals.
        rank: Sort by relevance (declarations first). Default True.
        output: "compact" (default) or "json" for structured list.
        cursor: Pagination cursor from previous call's next_cursor.

    Returns:
        compact or matches: References found.
        has_more: True if more results exist.
        next_cursor: Pass to next call to continue paginating.
        token_savings: Estimated tokens saved vs. reading files directly.
    """
    limit = max_results or settings.max_results

    raw, files_searched = _find_usages(
        symbol=symbol,
        directory=directory,
        extensions=extensions,
        exclude_comments=exclude_comments,
        exclude_strings=exclude_strings,
        rank=rank,
    )

    page, next_cursor, has_more = paginate(raw, limit, cursor, symbol)

    savings = TokenSavings(
        files_scanned=files_searched,
        estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
        note=(
            f"searched {files_searched} file(s), {len(page)} reference(s) to '{symbol}'"
            + (" [more available]" if has_more else "")
        ),
    )

    if output == "compact":
        return FindUsagesReport(
            compact=to_compact(page),
            has_more=has_more,
            next_cursor=next_cursor,
            token_savings=savings,
        )

    matches = [UsageMatch(**r) for r in page]
    return FindUsagesReport(
        matches=matches,
        has_more=has_more,
        next_cursor=next_cursor,
        token_savings=savings,
    )
