"""
Tool: audit_entrypoint

Détecte les imports actifs legacy dans ckeditor.js dont le symbole est
commenté ou absent dans builtinPlugins — candidats « à activer » sans migration profonde.
"""

from ckeditor_audit.lib.scanner import (
    EntrypointImportIssue,
    find_active_legacy_entrypoint_imports,
)


def audit_entrypoint() -> list[EntrypointImportIssue]:
    """
    Detect active legacy imports in ckeditor.js whose symbol is commented or missing
    in builtinPlugins.

    These are native CKEditor plugins (available in the flat 'ckeditor5' package) that
    require no deep migration — only update the import path and uncomment the entry.

    Returns an empty list when no entrypoint is configured or no issues are found.
    """
    return find_active_legacy_entrypoint_imports()
