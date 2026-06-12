from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_source as _find_source
from ckeditor_audit.tools.common import TokenSavings


class SourceMatch(BaseModel):
    path: str


class FindSourceReport(BaseModel):
    sources: list[SourceMatch]
    token_savings: TokenSavings


def find_source(test_path: str) -> FindSourceReport:
    """Find the source file corresponding to a test file (inverse of find_tests).

    Use this when navigating from a failing test to the implementation file.
    Examples:
      - tests/Domain/UserTest.php → src/Domain/User.php
      - src/components/Button.test.ts → src/components/Button.ts

    Args:
        test_path: Relative path to the test file (e.g. "tests/Domain/UserTest.php").

    Returns:
        sources: List of matching source file paths.
        token_savings: Estimated tokens saved vs. reading files directly.
    """
    raw = _find_source(test_path)
    savings = TokenSavings(
        files_scanned=len(raw),
        estimated_tokens_saved=len(raw) * 1200,
        note=f"mapped test→source, found {len(raw)} file(s)",
    )
    return FindSourceReport(sources=[SourceMatch(**r) for r in raw], token_savings=savings)
