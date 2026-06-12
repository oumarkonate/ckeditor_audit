from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_in_file_diff as _find_diff
from ckeditor_audit.tools.common import TokenSavings


class DiffHunk(BaseModel):
    path: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int


class FileDiffReport(BaseModel):
    hunks: list[DiffHunk]
    hint: str
    token_savings: TokenSavings


def find_in_file_diff(path: str, scope: str = "unstaged") -> FileDiffReport:
    """Return the modified line ranges (hunks) for a specific file from git diff.

    Use this before read_file when you only need to see what changed. It returns
    start line and line count for each modified section, so you can call
    read_file(path, start_line=hunk.new_start, end_line=...) targeted at changed code only.

    Args:
        path: Relative path to the file (e.g. "src/Domain/User.php").
        scope: Git diff scope — "unstaged" (default), "staged", or a commit SHA.

    Returns:
        hunks: Each hunk describes a modified region with old/new line coordinates.
        hint: Suggested read_file call to see the first changed section.
        token_savings: Estimated tokens saved vs. reading the whole file.
    """
    raw = _find_diff(path, scope)
    hunks = [DiffHunk(**h) for h in raw]

    hint = ""
    if hunks:
        h = hunks[0]
        end = h.new_start + max(h.new_lines - 1, 0)
        hint = (
            f"read_file('{path}', start_line={h.new_start}, "
            f"end_line={end + 20}) to see the first changed section"
        )

    savings = TokenSavings(
        files_scanned=1,
        estimated_tokens_saved=1200,
        note=f"git diff '{path}': {len(hunks)} hunk(s) — use start/end_line to read only changed sections",
    )
    return FileDiffReport(hunks=hunks, hint=hint, token_savings=savings)
