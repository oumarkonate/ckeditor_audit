from __future__ import annotations

from pydantic import BaseModel

from ckeditor_audit.lib.searcher import find_route as _find_route
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class RouteLocation(BaseModel):
    path: str
    line: int
    route: str
    methods: list[str]
    class_name: str = ""
    action: str = ""
    source: str = "attribute"


class FindRouteReport(BaseModel):
    results: list[RouteLocation]
    token_savings: TokenSavings


def find_route(pattern: str) -> FindRouteReport:
    """Find Symfony routes by path pattern substring.

    Searches all route definition sources:
    - PHP 8 attribute syntax: #[Route('/path', methods: ['GET'])]
    - Legacy @Route annotations (Symfony 4-5 docblocks)
    - YAML route files: config/routes.yaml and config/routes/*.yaml

    Args:
        pattern: Substring to match against route paths (e.g. "/api/users" or "/auth").

    Returns:
        results: Matching routes with path, line, route string, HTTP methods,
                 class name, action, and source ("attribute", "annotation", or "yaml").
        token_savings: Estimated tokens saved vs. reading all PHP/YAML files.
    """
    raw, files_searched = _find_route(pattern)
    results = [RouteLocation(**r) for r in raw]
    return FindRouteReport(
        results=results,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=(
                f"searched {files_searched} file(s) (PHP attributes, annotations, YAML), "
                f"found {len(results)} route(s) matching '{pattern}'"
            ),
        ),
    )
