from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_extends as _find_extends
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class ExtendsLocation(BaseModel):
    path: str
    line: int
    class_name: str
    namespace: str


class FindExtendsReport(BaseModel):
    results: list[ExtendsLocation]
    token_savings: TokenSavings


def find_extends(class_name: str) -> FindExtendsReport:
    """Find all PHP classes that directly extend a given class.

    Returns only direct children — call recursively to walk a full inheritance hierarchy.
    Handles fully qualified class names (e.g. `extends Vendor\\Base\\AbstractClass`).
    Searches only PHP files.

    Args:
        class_name: Exact class name to search for (e.g. "AbstractRepository").

    Returns:
        results: list of child classes with path, line number, class name, and namespace.
        token_savings: estimated tokens saved vs. Claude reading all PHP files directly.
    """
    raw, files_searched = _find_extends(class_name)
    results = [ExtendsLocation(**r) for r in raw]
    estimated_saved = files_searched * _TOKENS_PER_FILE
    return FindExtendsReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=estimated_saved,
            note=(
                f"searched {files_searched} PHP file(s), "
                f"found {len(results)} class(es) extending '{class_name}'"
            ),
        ),
    )
