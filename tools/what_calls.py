from pydantic import BaseModel

from ckeditor_audit.lib.searcher import what_calls as _what_calls
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class OutgoingCall(BaseModel):
    path: str
    line: int
    callee: str
    snippet: str


class WhatCallsReport(BaseModel):
    outgoing_calls: list[OutgoingCall]
    token_savings: TokenSavings


def what_calls(
    method: str,
    class_name: str | None = None,
) -> WhatCallsReport:
    """Find all functions/methods called by the given method (outgoing calls).

    Use this to understand what a method depends on without reading its full body.
    Complements who_calls — together they give you the call graph around a symbol.

    Args:
        method: Method or function name whose body to inspect for outgoing calls.
        class_name: Optional class name to disambiguate when multiple methods share the name.

    Returns:
        outgoing_calls: List of callees with their line, name, and snippet.
        token_savings: Estimated tokens saved vs reading the full method body.
    """
    raw, files_searched = _what_calls(method, class_name=class_name)
    calls = [OutgoingCall(**r) for r in raw]
    return WhatCallsReport(
        outgoing_calls=calls,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=f"{len(calls)} outgoing call(s) from '{method}'",
        ),
    )
