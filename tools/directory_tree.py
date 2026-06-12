from pydantic import BaseModel

from ckeditor_audit.lib.searcher import directory_tree as _directory_tree
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 80


class DirectoryTreeReport(BaseModel):
    tree: str
    token_savings: TokenSavings


def directory_tree(
    directory: str | None = None,
    depth: int = 3,
    extensions_filter: list[str] | None = None,
) -> DirectoryTreeReport:
    """Show the project directory tree as formatted text.

    Excluded directories (EXCLUDE_DIRS) are never traversed.

    Args:
        directory: Optional subdirectory to show (relative to project root). Defaults to project root.
        depth: Maximum depth to traverse (default: 3, max: 6).
        extensions_filter: Optional list of extensions — only files with these extensions are shown.
                           Directories are always shown. E.g. ["php", "yaml"].

    Returns:
        tree: Formatted directory tree as a string.
        token_savings: estimated tokens saved vs. Claude listing directories recursively.
    """
    tree, files_traversed = _directory_tree(directory, depth, extensions_filter)
    estimated_saved = files_traversed * _TOKENS_PER_FILE
    return DirectoryTreeReport(
        tree=tree,
        token_savings=TokenSavings(
            files_scanned=files_traversed,
            estimated_tokens_saved=estimated_saved,
            note=f"traversed {files_traversed} file(s), depth={depth}",
        ),
    )
