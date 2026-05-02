"""
Tools: git_changed_files, grep_changed

Git-aware search tools that operate only on files modified in the working tree.
Ideal for targeted audits after a migration step, or for catching regressions
introduced by recent changes.
"""

from pathlib import Path

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.searcher import (
    TOKENS_PER_FILE_FIND,
    TOKENS_PER_FILE_SEARCH,
    git_list_changed,
    grep_specific_files,
)
from ckeditor_audit.tools.common import TokenSavings


# ---------------------------------------------------------------------------
# git_changed_files
# ---------------------------------------------------------------------------

class ChangedFile(BaseModel):
    path: str    # relative to project root
    status: str  # M=modified, A=added, D=deleted, R=renamed


class GitChangedFilesReport(BaseModel):
    results: list[ChangedFile]
    token_savings: TokenSavings


def git_changed_files(scope: str = "unstaged") -> GitChangedFilesReport:
    """
    List files changed in the git working tree.

    `scope` accepts:
    - "unstaged" (default): changes in the working directory, not yet staged
    - "staged": changes staged for the next commit
    - "all": both staged and unstaged (equivalent to git status)
    - a commit SHA: files changed in that specific commit

    Requires the project root to be inside a git repository.
    Returns an empty list if git is unavailable or the repo is clean.
    """
    changed = git_list_changed(scope)
    results = [ChangedFile(path=path, status=status) for status, path in changed]

    return GitChangedFilesReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=len(results),
            estimated_tokens_saved=len(results) * TOKENS_PER_FILE_FIND,
            note=(
                f"found {len(results)} changed file(s) "
                f"(scope: {scope!r})"
            ),
        ),
    )


# ---------------------------------------------------------------------------
# grep_changed
# ---------------------------------------------------------------------------

class GrepChangedMatch(BaseModel):
    path: str     # relative to project root
    line: int     # 1-based line number
    snippet: str  # matched line content, truncated to 120 chars


class GrepChangedReport(BaseModel):
    matches: list[GrepChangedMatch]
    token_savings: TokenSavings


def grep_changed(
    query: str,
    scope: str = "unstaged",
    extensions: list[str] | None = None,
) -> GrepChangedReport:
    """
    Search for `query` only in git-changed files.

    Much faster than grep_code for post-migration checks: instead of scanning
    the entire project, it restricts the search to files that were actually
    modified (according to `scope`).

    Deleted files are automatically skipped.
    `extensions` narrows the search further, e.g. ["js", "ts"].
    `scope` works the same as in git_changed_files.
    """
    root = settings.project_root
    changed = git_list_changed(scope)

    if not changed:
        return GrepChangedReport(
            matches=[],
            token_savings=TokenSavings(
                files_scanned=0,
                estimated_tokens_saved=0,
                note=f"no changed files found (scope: {scope!r})",
            ),
        )

    ext_set = {e.lstrip(".").lower() for e in extensions} if extensions else None

    candidate_paths: list[Path] = []
    for status, rel_path in changed:
        if status == "D":
            continue
        full = root / rel_path
        if not full.is_file():
            continue
        if ext_set and Path(rel_path).suffix.lstrip(".").lower() not in ext_set:
            continue
        candidate_paths.append(full)

    if not candidate_paths:
        return GrepChangedReport(
            matches=[],
            token_savings=TokenSavings(
                files_scanned=0,
                estimated_tokens_saved=0,
                note="no candidate files after filtering (all deleted or wrong extension)",
            ),
        )

    raw = grep_specific_files(query, candidate_paths)
    matches = [
        GrepChangedMatch(path=m.path, line=m.line, snippet=m.snippet)
        for m in raw
    ]

    return GrepChangedReport(
        matches=matches,
        token_savings=TokenSavings(
            files_scanned=len(candidate_paths),
            estimated_tokens_saved=len(candidate_paths) * TOKENS_PER_FILE_SEARCH,
            note=(
                f"searched {len(candidate_paths)} changed file(s) "
                f"(scope: {scope!r}), found {len(matches)} match(es) for '{query}'"
            ),
        ),
    )
