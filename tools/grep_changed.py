from pydantic import BaseModel

from ckeditor_audit.lib.searcher import grep_changed as _grep_changed
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class GrepChangedMatch(BaseModel):
    path: str
    line: int
    snippet: str


class GrepChangedReport(BaseModel):
    matches: list[GrepChangedMatch]
    token_savings: TokenSavings


def grep_changed(
    query: str,
    scope: str = "unstaged",
    extensions: list[str] | None = None,
) -> GrepChangedReport:
    """Search for a pattern only in files modified by git.

    Combines git_changed_files with grep_code — searches only the current diff,
    not the entire project. Returns immediately if there are no changed files.
    Requires CKEDITOR_AUDIT_PROJECT_ROOT to be inside a git repository.

    Args:
        query: Regex pattern (or plain text) to search for.
        scope: Which changes to search in: "unstaged" (default), "staged", "all", or a commit SHA.
        extensions: Optional list of file extensions to restrict the search, e.g. ["php", "ts"].

    Returns:
        matches: list of matches with file path, line number, and a short snippet.
        token_savings: estimated tokens saved vs. Claude reading the changed files directly.
    """
    raw, files_searched = _grep_changed(query, scope, extensions)
    matches = [GrepChangedMatch(**r) for r in raw]
    estimated_saved = files_searched * _TOKENS_PER_FILE
    return GrepChangedReport(
        matches=matches,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=estimated_saved,
            note=(
                f"searched {files_searched} changed file(s) [{scope}], "
                f"found {len(matches)} match(es)"
            ),
        ),
    )
