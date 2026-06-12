from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_tests as _find_tests
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 80


class TestMatch(BaseModel):
    path: str
    framework: str


class FindTestsReport(BaseModel):
    results: list[TestMatch]
    token_savings: TokenSavings


def find_tests(source_path: str) -> FindTestsReport:
    """Find test files corresponding to a source file.

    Works for PHP (PHPUnit), JS/TS (Jest), and Playwright.

    Args:
        source_path: Relative path to the source file (e.g. "src/Domain/Services/Content.php")
                     or just a file name (e.g. "Content.php").

    Returns:
        results: list of test files with their relative path and the test framework name.
        token_savings: estimated tokens saved vs. Claude searching test directories directly.
    """
    raw = _find_tests(source_path)
    results = [TestMatch(**r) for r in raw]
    return FindTestsReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=1,
            estimated_tokens_saved=_TOKENS_PER_FILE,
            note=f"located {len(results)} test file(s) for '{source_path}'",
        ),
    )
