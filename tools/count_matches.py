from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import count_matches as _count_matches
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class CountMatchesReport(BaseModel):
    total_matches: int
    files_matched: int
    files_searched: int
    suggestion: str | None = None
    token_savings: TokenSavings


def count_matches(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    whole_word: bool = False,
    fixed_string: bool = False,
    case_sensitive: bool | str = "smart",
    path_glob: str | None = None,
) -> CountMatchesReport:
    """Count occurrences of a pattern without fetching all results.

    Use this BEFORE grep_code when you suspect there may be many matches and want to
    decide whether to refine the pattern first. If total_matches > max_results, add
    whole_word=True, a directory, or a path_glob to narrow down.

    Args:
        query: Regex pattern (or plain text) to count.
        directory: Optional subdirectory to restrict the search.
        extensions: Optional file extensions to search.
        whole_word: Match whole words only.
        fixed_string: Treat query as literal string.
        case_sensitive: True, False, or "smart".
        path_glob: Glob pattern like "src/**/*.php".

    Returns:
        total_matches: Total pattern occurrences.
        files_matched: Files with at least one match.
        files_searched: Total files scanned.
        suggestion: Advice when total_matches is very large.
        token_savings: Estimated tokens saved vs. reading files.
    """
    raw = _count_matches(
        query=query,
        directory=directory,
        extensions=extensions,
        whole_word=whole_word,
        fixed_string=fixed_string,
        case_sensitive=case_sensitive,
        path_glob=path_glob,
    )
    files_searched = raw["files_searched"]
    total = raw["total_matches"]
    limit = settings.max_results

    suggestion = None
    if total > limit * 5:
        suggestion = (
            f"{total} matches found. Consider adding whole_word=True, "
            "a directory filter, or a path_glob to narrow results before running grep_code."
        )

    return CountMatchesReport(
        **raw,
        suggestion=suggestion,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=(
                f"backend={'rg' if settings.backend == 'rg' else 'python'}, "
                f"{files_searched} file(s) searched, {total} match(es) in {raw['files_matched']} file(s)"
            ),
        ),
    )
