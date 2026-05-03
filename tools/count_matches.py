"""
Tool: count_matches

Counts occurrences of a pattern across project files without returning snippets.
Use this before grep_code to gauge the scope of a search.
"""

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import TOKENS_PER_FILE_SEARCH, count_pattern
from ckeditor_audit.tools.common import TokenSavings


class CountMatchesReport(BaseModel):
    total_matches: int   # total number of matching lines across all files
    files_matched: int   # number of files that contain at least one match
    files_searched: int  # total number of files scanned
    token_savings: TokenSavings


def count_matches(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
) -> CountMatchesReport:
    """
    Count occurrences of `query` across project files without returning snippets.

    Useful before calling grep_code: if total_matches is large, narrow your
    search with `directory` or `extensions` filters, or refine the regex.

    `query` follows the same regex-or-literal rules as grep_code.
    """
    total, files_matched, files_searched = count_pattern(query, directory, extensions)

    return CountMatchesReport(
        total_matches=total,
        files_matched=files_matched,
        files_searched=files_searched,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * TOKENS_PER_FILE_SEARCH,
            note=(
                f"scanned {files_searched} file(s): "
                f"{total} match(es) across {files_matched} file(s) for '{query}'"
            ),
        ),
    )
