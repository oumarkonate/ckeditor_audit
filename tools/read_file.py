from pydantic import BaseModel

from ckeditor_audit.lib.searcher import read_file as _read_file
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class ReadFileResult(BaseModel):
    content: str
    total_lines: int
    token_savings: TokenSavings


def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> ReadFileResult:
    """Read a file's content with an optional line range.

    Args:
        path: Relative path from project root (e.g. "src/Domain/Services/ContentService.php").
        start_line: First line to read, 1-indexed. Defaults to 1.
        end_line: Last line to read, inclusive, 1-indexed. Defaults to start_line + 199.

    Returns:
        content: File content for the requested range.
        total_lines: Total number of lines in the file.
        token_savings: estimated tokens saved vs. Claude reading the full file directly.
    """
    content, total_lines = _read_file(path, start_line, end_line)
    return ReadFileResult(
        content=content,
        total_lines=total_lines,
        token_savings=TokenSavings(
            files_scanned=1,
            estimated_tokens_saved=_TOKENS_PER_FILE,
            note=f"read {path} ({total_lines} lines total)",
        ),
    )
