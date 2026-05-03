"""
Tool: grep_code

Searches project files for a regex pattern (or plain text).
Returns one match per line with a short snippet.
"""

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import TOKENS_PER_FILE_SEARCH, grep_files
from ckeditor_audit.tools.common import TokenSavings


class GrepMatch(BaseModel):
    """A single line match."""

    path: str     # relative to project root
    line: int     # 1-based line number
    snippet: str  # matched line content, truncated to 120 chars


class GrepCodeReport(BaseModel):
    matches: list[GrepMatch]
    token_savings: TokenSavings


def grep_code(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
) -> GrepCodeReport:
    """
    Search project files for `query` (regex or plain text).

    `query` is first compiled as a Python regex. If the syntax is invalid,
    it is treated as a literal string — so plain text always works.

    `directory` restricts the search to a subdirectory relative to the project root.
    `extensions` filters by file extension, e.g. ["js", "ts"].
    `max_results` caps returned matches (defaults to CKEDITOR_AUDIT_MAX_RESULTS).

    Returns one match per line. Snippet is truncated to 120 characters.
    Use grep_with_context when you need surrounding lines to understand a hit.
    """
    raw, files_searched = grep_files(query, directory, extensions, max_results)

    matches = [
        GrepMatch(path=m.path, line=m.line, snippet=m.snippet)
        for m in raw
    ]

    return GrepCodeReport(
        matches=matches,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * TOKENS_PER_FILE_SEARCH,
            note=(
                f"searched {files_searched} file(s), "
                f"found {len(matches)} match(es) for '{query}'"
            ),
        ),
    )
