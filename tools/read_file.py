"""
Tool: read_file

Reads a project file by its path relative to project root.
Returns a 200-line chunk by default; use start_line/end_line for large files.
"""

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.searcher import TOKENS_PER_FILE_SEARCH
from ckeditor_audit.tools.common import TokenSavings

_DEFAULT_CHUNK = 200


class ReadFileResult(BaseModel):
    content: str       # file content, lines prefixed with their number
    total_lines: int   # total lines in the file (useful to detect truncation)
    token_savings: TokenSavings


def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> ReadFileResult:
    """
    Read a project file (path relative to project root).

    Returns at most 200 lines by default, starting from line 1.
    Use `start_line` and `end_line` (1-indexed, inclusive) to read a specific
    range. Check `total_lines` to know whether more content exists beyond the
    returned chunk.

    Lines are prefixed with their line number for easy navigation,
    e.g. "42: import { Plugin } from 'ckeditor5'".
    """
    full_path = settings.project_root / path

    if not full_path.is_file():
        return ReadFileResult(
            content=f"File not found: {path}",
            total_lines=0,
            token_savings=TokenSavings(
                files_scanned=0,
                estimated_tokens_saved=0,
                note="file not found — check the path relative to project root",
            ),
        )

    try:
        lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        return ReadFileResult(
            content=f"Error reading file: {exc}",
            total_lines=0,
            token_savings=TokenSavings(
                files_scanned=0,
                estimated_tokens_saved=0,
                note="OS error while reading file",
            ),
        )

    total = len(lines)
    start = max(1, start_line or 1)
    end = min(end_line or (start + _DEFAULT_CHUNK - 1), total)

    chunk = lines[start - 1 : end]
    content = "\n".join(f"{start + i}: {line}" for i, line in enumerate(chunk))

    return ReadFileResult(
        content=content,
        total_lines=total,
        token_savings=TokenSavings(
            files_scanned=1,
            estimated_tokens_saved=TOKENS_PER_FILE_SEARCH,
            note=(
                f"read lines {start}–{end} of {total} in '{path}'"
                + (f" ({total - end} lines remaining)" if end < total else "")
            ),
        ),
    )
