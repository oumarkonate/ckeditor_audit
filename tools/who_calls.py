from pydantic import BaseModel

from ckeditor_audit.lib.searcher import who_calls as _who_calls
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class CallSite(BaseModel):
    path: str
    line: int
    snippet: str
    caller: str | None = None


class WhoCallsReport(BaseModel):
    call_sites: list[CallSite]
    token_savings: TokenSavings


def who_calls(
    method: str,
    class_name: str | None = None,
    directory: str | None = None,
) -> WhoCallsReport:
    """Find all call sites of a method or function across the project.

    Use this instead of grep_code("methodName(") — it also identifies the enclosing
    caller function/method so you can understand the call graph without reading files.

    Args:
        method: Method or function name to find call sites for.
        class_name: Optional class context (not yet used for disambiguation, reserved for future).
        directory: Optional subdirectory to restrict the search.

    Returns:
        call_sites: Each call site with path, line, snippet, and caller function name.
        token_savings: Estimated tokens saved vs manual grep + file reads.
    """
    raw, files_searched = _who_calls(method, class_name=class_name, directory=directory)
    call_sites = [CallSite(**r) for r in raw]
    return WhoCallsReport(
        call_sites=call_sites,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=f"searched {files_searched} file(s), {len(call_sites)} call site(s)",
        ),
    )
