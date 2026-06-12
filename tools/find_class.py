from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_class as _find_class
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class ClassLocation(BaseModel):
    path: str
    line: int
    kind: str
    namespace: str
    fuzzy_score: int | None = None


class FindClassReport(BaseModel):
    results: list[ClassLocation]
    token_savings: TokenSavings


def find_class(
    class_name: str,
    kind: str | None = None,
    fuzzy: bool = False,
) -> FindClassReport:
    """Locate a PHP class, interface, trait, or enum declaration by name.

    Uses ast-grep for precise multiline declaration detection when available
    (handles 'class X implements A,\\n  B' correctly).

    Prefer find_definition when you're not sure if it's a class or a function —
    that tool tries all kinds in one call.

    Args:
        class_name: Exact class name (e.g. "ContentRepository"). Use fuzzy=True for partial matches.
        kind: Optional filter: "class", "interface", "trait", or "enum".
        fuzzy: If True, find classes whose names partially match class_name (e.g. "ContentRepo" finds "ContentRepository").

    Returns:
        results: Declarations found, with path, line, kind, namespace. Fuzzy results include a score.
        token_savings: Estimated tokens saved vs. reading all PHP files directly.
    """
    raw, files_searched = _find_class(class_name, kind=kind, fuzzy=fuzzy)
    # Clean up internal name_key field used by fuzzy
    results = [
        ClassLocation(
            path=r.get("path", ""),
            line=r.get("line", 0),
            kind=r.get("kind", "class"),
            namespace=r.get("namespace", ""),
            fuzzy_score=r.get("fuzzy_score"),
        )
        for r in raw
    ]
    backend = "ast-grep" if settings.ast_grep_available else "regex"
    return FindClassReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=(
                f"backend={backend}, searched {files_searched} PHP file(s), "
                f"found {len(results)} declaration(s) of '{class_name}'"
            ),
        ),
    )
