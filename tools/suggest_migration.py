"""
Tool: suggest_migration

For each legacy pattern detected in a plugin, return a concrete actionable fix:
the exact line to change, the legacy signature found, and the modern replacement.
"""

from pydantic import BaseModel

from ckeditor_audit.lib.constants import TOKENS_PER_PLUGIN_FILE
from ckeditor_audit.lib.scanner import find_pattern_hits
from ckeditor_audit.tools.common import TokenSavings


class MigrationFix(BaseModel):
    """One actionable migration fix for a detected legacy pattern."""

    file: str
    line: int
    category: str
    legacy: str
    replacement: str
    description: str


class SuggestMigrationReport(BaseModel):
    plugin: str
    fixes: list[MigrationFix]
    total_fixes: int
    token_savings: TokenSavings


def suggest_migration(plugin: str) -> SuggestMigrationReport:
    """
    Return concrete, actionable migration fixes for a CKEditor plugin.

    For each legacy import or API pattern detected, returns the exact file,
    line number, legacy signature, and its modern replacement — ready to apply.

    Use this after `audit_plugin` to get the precise changes needed.
    Use `validate_migration` afterwards to confirm no legacy signatures remain.

    `plugin` must be the plugin directory name, e.g. "ckeditor5-box".
    """
    hits = find_pattern_hits(plugin)

    # Count distinct files touched, for the token-savings estimate.
    files_count = len({h.file for h in hits})

    fixes = [
        MigrationFix(
            file=h.file,
            line=h.line,
            category=h.pattern.category,
            legacy=h.matched,
            replacement=h.pattern.replacement,
            description=h.pattern.description,
        )
        for h in hits
    ]

    return SuggestMigrationReport(
        plugin=plugin,
        fixes=fixes,
        total_fixes=len(fixes),
        token_savings=TokenSavings(
            files_scanned=files_count,
            estimated_tokens_saved=files_count * TOKENS_PER_PLUGIN_FILE,
            note=(
                f"found {len(fixes)} fix(es) across {files_count} file(s) in '{plugin}'"
            ),
        ),
    )
