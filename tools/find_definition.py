from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_definition as _find_definition
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class DefinitionMatch(BaseModel):
    path: str
    line: int
    kind: str | None = None
    namespace: str | None = None
    class_name: str | None = None
    visibility: str | None = None


class FindDefinitionReport(BaseModel):
    matches: list[DefinitionMatch]
    token_savings: TokenSavings


def find_definition(
    name: str,
    kind: str | None = None,
) -> FindDefinitionReport:
    """Find the declaration of any symbol in one call — class, interface, function, method, or route.

    Prefer this over chaining find_class + find_method + grep_code. It tries each lookup
    in order of specificity and returns as soon as it finds results.

    Args:
        name: Symbol name to look up (class name, method name, route path fragment, etc.).
        kind: Optional hint — "class", "interface", "trait", "enum", "method", "function", "route".
              If omitted, all kinds are tried in order.

    Returns:
        matches: Declaration(s) found, sorted by likelihood.
        token_savings: Estimated tokens saved vs. chained manual lookups.
    """
    raw, files_searched = _find_definition(name, kind=kind)
    matches = []
    for r in raw:
        matches.append(DefinitionMatch(
            path=r.get("path", ""),
            line=r.get("line", 0),
            kind=r.get("kind"),
            namespace=r.get("namespace"),
            class_name=r.get("class_name"),
            visibility=r.get("visibility"),
        ))
    return FindDefinitionReport(
        matches=matches,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=f"searched {files_searched} file(s), found {len(matches)} definition(s)",
        ),
    )
