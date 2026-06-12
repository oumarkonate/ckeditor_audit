from pydantic import BaseModel

from ckeditor_audit.lib.searcher import git_changed_files as _git_changed_files
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 80


class ChangedFile(BaseModel):
    path: str
    status: str


class GitChangedFilesReport(BaseModel):
    results: list[ChangedFile]
    token_savings: TokenSavings


def git_changed_files(scope: str = "unstaged") -> GitChangedFilesReport:
    """List files modified in the git working tree.

    Requires CKEDITOR_AUDIT_PROJECT_ROOT to be inside a git repository.

    Args:
        scope: Which changes to list:
               "unstaged" (default) — working tree changes not yet staged,
               "staged"             — changes staged for the next commit,
               "all"                — both staged and unstaged (git status),
               "<SHA>"              — files changed in a specific commit.

    Returns:
        results: list of changed files with their relative path and git status code
                 (M = modified, A = added, D = deleted, R = renamed).
        token_savings: estimated tokens saved vs. Claude running git commands directly.
    """
    raw = _git_changed_files(scope)
    results = [ChangedFile(**f) for f in raw]
    estimated_saved = len(results) * _TOKENS_PER_FILE
    return GitChangedFilesReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=len(results),
            estimated_tokens_saved=estimated_saved,
            note=f"found {len(results)} changed file(s) [{scope}]",
        ),
    )
