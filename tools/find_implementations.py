from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_implementations as _find_implementations
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class ImplementationLocation(BaseModel):
    path: str
    line: int
    class_name: str
    namespace: str


class FindImplementationsReport(BaseModel):
    results: list[ImplementationLocation]
    token_savings: TokenSavings


def find_implementations(interface_name: str) -> FindImplementationsReport:
    """Find all PHP classes that implement a given interface.

    Uses ast-grep when available — correctly handles multiline declarations:
      class X implements A,
          InterfaceName, B { ... }

    Falls back to multiline-safe regex when ast-grep is unavailable.

    Args:
        interface_name: Exact interface name (e.g. "ContentRepositoryInterface").

    Returns:
        results: Implementing classes with path, line, class name, namespace.
        token_savings: Estimated tokens saved vs. reading all PHP files.
    """
    raw, files_searched = _find_implementations(interface_name)
    results = [ImplementationLocation(**r) for r in raw]
    backend = "ast-grep" if settings.ast_grep_available else "regex"
    return FindImplementationsReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=(
                f"backend={backend}, searched {files_searched} PHP file(s), "
                f"found {len(results)} implementation(s) of '{interface_name}'"
            ),
        ),
    )
