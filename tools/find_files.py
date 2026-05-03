"""
Tool: find_files

Finds project files whose name contains a given pattern.
No content scanning — pure name matching.
"""

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.searcher import TOKENS_PER_FILE_FIND, find_files_by_name
from ckeditor_audit.tools.common import TokenSavings


class FileInfo(BaseModel):
    """A file that matched the name search."""

    path: str   # relative to project root
    name: str   # filename only


class FindFilesReport(BaseModel):
    results: list[FileInfo]
    token_savings: TokenSavings


def find_files(
    pattern: str,
    directory: str | None = None,
    extension: str | None = None,
) -> FindFilesReport:
    """
    Find project files whose name contains `pattern` (case-insensitive).

    `directory` restricts the search to a subdirectory relative to the project root.
    `extension` filters by file extension, e.g. "js" or "yaml" (no leading dot needed).

    Returns up to CKEDITOR_AUDIT_MAX_RESULTS matches.
    """
    root = settings.project_root
    paths, files_checked = find_files_by_name(pattern, directory, extension)

    results = [
        FileInfo(path=str(p.relative_to(root)), name=p.name)
        for p in paths
    ]

    return FindFilesReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=files_checked,
            estimated_tokens_saved=files_checked * TOKENS_PER_FILE_FIND,
            note=(
                f"checked {files_checked} file(s), "
                f"found {len(results)} match(es) for name pattern '{pattern}'"
            ),
        ),
    )
