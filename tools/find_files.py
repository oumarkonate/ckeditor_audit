from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_files as _find_files
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 80


class FileMatch(BaseModel):
    path: str
    name: str


class FindFilesReport(BaseModel):
    results: list[FileMatch]
    token_savings: TokenSavings


def find_files(
    pattern: str,
    directory: str | None = None,
    extension: str | None = None,
) -> FindFilesReport:
    """Find files whose name contains the given pattern.

    Args:
        pattern: Substring to search for in file names (case-insensitive).
        directory: Optional subdirectory to restrict the search (relative to project root).
        extension: Optional file extension filter, e.g. "php" or "ts".

    Returns:
        results: list of matching files with their relative path and name.
        token_savings: estimated tokens saved vs. Claude running a bash find + filtering.
    """
    raw, files_checked = _find_files(pattern, directory, extension)
    results = [FileMatch(**r) for r in raw]
    estimated_saved = files_checked * _TOKENS_PER_FILE
    return FindFilesReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=files_checked,
            estimated_tokens_saved=estimated_saved,
            note=(
                f"checked {files_checked} file(s), "
                f"returned {len(results)} match(es) for '{pattern}'"
            ),
        ),
    )