"""
Tool: audit_all

Returns a lightweight summary of migration status for every detected plugin.
Intentionally minimal — no issue details. Use audit_plugin for a deep dive.
"""

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.scanner import detect_status, list_plugins, plugin_files
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_SOURCE_FILE = 500


class PluginSummary(BaseModel):
    """One row in the global migration report."""

    plugin: str
    status: str    # "migrated" | "not_migrated" | "partial"


class AuditAllReport(BaseModel):
    """Global migration report."""

    total: int
    migrated: int
    partial: int
    not_migrated: int
    legacy_label: str
    target_label: str
    plugins: list[PluginSummary]
    token_savings: TokenSavings


def audit_all() -> AuditAllReport:
    """
    Return the migration status for all detected CKEditor plugins.

    Counts are included for a quick overview. Use audit_plugin(name) to get
    the detailed issue list for any individual plugin.
    """
    plugins = list_plugins()
    summaries: list[PluginSummary] = []
    total_source_files = 0

    for name in plugins:
        status = detect_status(name)
        summaries.append(PluginSummary(plugin=name, status=status))
        total_source_files += len(plugin_files(name))

    migrated_count = sum(1 for s in summaries if s.status == "migrated")
    partial_count = sum(1 for s in summaries if s.status == "partial")
    not_migrated_count = sum(1 for s in summaries if s.status == "not_migrated")

    estimated_saved = total_source_files * _TOKENS_PER_SOURCE_FILE

    return AuditAllReport(
        total=len(summaries),
        migrated=migrated_count,
        partial=partial_count,
        not_migrated=not_migrated_count,
        legacy_label=settings.legacy_label,
        target_label=settings.target_label,
        plugins=summaries,
        token_savings=TokenSavings(
            files_scanned=total_source_files,
            estimated_tokens_saved=estimated_saved,
            note=(
                f"scanned {total_source_files} source file(s) across "
                f"{len(plugins)} plugin(s) instead of Claude reading them directly"
            ),
        ),
    )