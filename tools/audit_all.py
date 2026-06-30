"""
Tool: audit_all

Returns a lightweight summary of migration status for every detected plugin.
Intentionally minimal — no issue details. Use audit_plugin for a deep dive.
"""

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.scanner import (
    EntrypointImportIssue,
    detect_status,
    find_active_legacy_entrypoint_imports,
    list_plugins,
    load_overrides,
    parse_entrypoint,
    plugin_files,
)
from ckeditor_audit.lib.constants import TOKENS_PER_SOURCE_FILE
from ckeditor_audit.tools.common import TokenSavings


class PluginSummary(BaseModel):
    """One row in the global migration report."""

    plugin: str
    # migrated | not_migrated | partial | no_imports |
    # to_delete | requires_reimplementation | aliased_to
    status: str
    # Free-text note from .ckeditor-audit.json (override reason), if any.
    reason: str = ""
    # Renamed target from an `aliased_to` override, if any.
    aliased_to: str = ""
    # Entrypoint cross-check: True = referenced active, False = commented only,
    # None = not found in entrypoint or no entrypoint configured.
    entrypoint_active: bool | None = None


class AuditAllReport(BaseModel):
    """Global migration report."""

    total: int
    migrated: int
    partial: int
    not_migrated: int
    no_imports: int
    to_delete: int
    requires_reimplementation: int
    legacy_label: str
    target_label: str
    plugins: list[PluginSummary]
    token_savings: TokenSavings
    to_activate_imports: int = 0
    entrypoint_issues: list[EntrypointImportIssue] = []


def audit_all() -> AuditAllReport:
    """
    Return the migration status for all detected CKEditor plugins.

    Counts are included for a quick overview. Use audit_plugin(name) to get
    the detailed issue list for any individual plugin.
    """
    plugins = list_plugins()
    overrides = load_overrides()
    entry = parse_entrypoint()
    summaries: list[PluginSummary] = []
    total_source_files = 0

    for name in plugins:
        status = detect_status(name)
        # `skip` plugins are excluded from the report entirely.
        if status == "skip":
            continue

        ovr = overrides.get(name)
        if name in entry["active"]:
            entrypoint_active: bool | None = True
        elif name in entry["commented"]:
            entrypoint_active = False
        else:
            entrypoint_active = None

        summaries.append(
            PluginSummary(
                plugin=name,
                status=status,
                reason=ovr.reason if ovr else "",
                aliased_to=ovr.aliased_to if ovr else "",
                entrypoint_active=entrypoint_active,
            )
        )
        total_source_files += len(plugin_files(name))

    migrated_count = sum(1 for s in summaries if s.status == "migrated")
    partial_count = sum(1 for s in summaries if s.status == "partial")
    not_migrated_count = sum(1 for s in summaries if s.status == "not_migrated")
    no_imports_count = sum(1 for s in summaries if s.status == "no_imports")
    # aliased_to plugins are reported alongside to_delete ("à supprimer").
    to_delete_count = sum(
        1 for s in summaries if s.status in ("to_delete", "aliased_to")
    )
    reimpl_count = sum(
        1 for s in summaries if s.status == "requires_reimplementation"
    )

    estimated_saved = total_source_files * TOKENS_PER_SOURCE_FILE
    entrypoint_issues = find_active_legacy_entrypoint_imports()

    return AuditAllReport(
        total=len(summaries),
        migrated=migrated_count,
        partial=partial_count,
        not_migrated=not_migrated_count,
        no_imports=no_imports_count,
        to_delete=to_delete_count,
        requires_reimplementation=reimpl_count,
        legacy_label=settings.legacy_label,
        target_label=settings.target_label,
        plugins=summaries,
        to_activate_imports=len(entrypoint_issues),
        entrypoint_issues=entrypoint_issues,
        token_savings=TokenSavings(
            files_scanned=total_source_files,
            estimated_tokens_saved=estimated_saved,
            note=(
                f"scanned {total_source_files} source file(s) across "
                f"{len(plugins)} plugin(s) instead of Claude reading them directly"
            ),
        ),
    )