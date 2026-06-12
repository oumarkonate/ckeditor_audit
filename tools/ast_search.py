from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 1200


class AstMatch(BaseModel):
    path: str
    line: int
    snippet: str


class AstSearchReport(BaseModel):
    matches: list[AstMatch]
    token_savings: TokenSavings


def ast_search(
    pattern: str,
    lang: str,
    path_glob: str | None = None,
    directory: str | None = None,
    max_results: int | None = None,
) -> AstSearchReport:
    """Search for a structural AST pattern using ast-grep.

    Use this instead of grep_code when you need to match code *structure*, not text:
    - Find all function declarations with specific signatures
    - Find method calls with specific argument patterns
    - Find class definitions implementing certain patterns

    Patterns use ast-grep syntax: $VAR matches any single node, $$$VARS matches multiple.
    Example patterns:
      - PHP: "class $NAME implements $IFACE" matches any class implementing anything
      - PHP: "function $NAME($$$PARAMS): $RETURN { $$$BODY }"
      - TS: "const $NAME = ($$$) => $$$"

    Args:
        pattern: ast-grep structural pattern with $VAR wildcards.
        lang: Language — "php", "javascript", "typescript", "tsx".
        path_glob: Optional glob to restrict files, e.g. "src/**/*.php".
        directory: Optional subdirectory relative to project root.
        max_results: Max number of matches (defaults to CKEDITOR_AUDIT_MAX_RESULTS).

    Returns:
        matches: List of structural matches with path, line, and matched code snippet.
        token_savings: Estimated tokens saved vs manual file reads.
    """
    if not settings.ast_grep_available:
        raise RuntimeError(
            "ast-grep-py is not installed. Run: pip install ast-grep-py"
        )

    from ckeditor_audit.lib.backends.astgrep import ast_search as _ast_search

    limit = max_results or settings.max_results
    raw, files_searched = _ast_search(
        pattern=pattern,
        lang=lang,
        root=settings.project_root,
        path_glob=path_glob,
        directory=directory,
        extensions=settings.extensions,
        exclude_dirs=settings.exclude_dirs,
        max_results=limit,
    )
    matches = [AstMatch(**r) for r in raw]
    return AstSearchReport(
        matches=matches,
        token_savings=TokenSavings(
            files_scanned=files_searched,
            estimated_tokens_saved=files_searched * _TOKENS_PER_FILE,
            note=(
                f"ast-grep structural search on {files_searched} file(s), "
                f"{len(matches)} match(es)"
            ),
        ),
    )
