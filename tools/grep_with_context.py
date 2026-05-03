"""
Tool: grep_with_context

Same as grep_code but each match includes surrounding lines for context.
Useful for verifying whether a legacy pattern hit is genuine before acting.
"""

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import TOKENS_PER_FILE_SEARCH, grep_files_with_context
from ckeditor_audit.tools.common import TokenSavings


class ContextMatch(BaseModel):
    """A match with its surrounding lines."""

    path: str          # relative to project root
    line: int          # 1-based line number of the match
    snippet: str       # matched line content, truncated to 120 chars
    before: list[str]  # lines immediately before the match
    after: list[str]   # lines immediately after the match


class GrepContextReport(BaseModel):
    matches: list[ContextMatch]
    token_savings: TokenSavings


def grep_with_context(
    query: str,
    context_lines: int = 3,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
) -> GrepContextReport:
    """
    Search project files for `query` and return surrounding lines for context.

    Works identically to grep_code but each match includes up to `context_lines`
    lines before and after the matching line (clamped to [0, 10]).

    Use this tool when a match from grep_code needs verification — for example,
    to check whether a legacy pattern is inside a comment, a string literal,
    or a genuine import statement.
    """
    raw, files_searched = grep_files_with_context(
        query, context_lines, directory, extensions, max_results
    )

    matches = [
        ContextMatch(
            path=m.path,
            line=m.line,
            snippet=m.snippet,
            before=m.before,
            after=m.after,
        )
        for m in raw
    ]

    ctx = max(0, min(context_lines, 10))
    return GrepContextReport(
        matches=matches,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * TOKENS_PER_FILE_SEARCH,
            note=(
                f"searched {files_searched} file(s), "
                f"found {len(matches)} match(es) with ±{ctx} context lines"
            ),
        ),
    )
