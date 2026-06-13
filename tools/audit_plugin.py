"""
Tool: audit_plugin

Returns a detailed migration report for a single plugin.
The return type is a Pydantic BaseModel — MCPServer automatically generates
its JSON schema and Claude receives a validated, structured response.
"""

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.scanner import (
    configs_using,
    detect_status,
    find_pattern_hits,
    plugin_files,
    plugin_package_info,
    plugin_root,
)
from ckeditor_audit.lib.constants import (
    TOKENS_PER_CONFIG_FILE,
    TOKENS_PER_SOURCE_FILE,
)
from ckeditor_audit.tools.common import TokenSavings


class Issue(BaseModel):
    """One legacy pattern hit found in the plugin source."""

    file: str    # relative path inside the plugin (e.g. "src/box.js")
    line: int    # 1-based line number
    legacy: str          # the legacy signature that was matched
    replacement: str     # the suggested modern equivalent
    description: str     # plain-English explanation
    category: str        # import | api | schema | utils


class ConfigUsage(BaseModel):
    """How a plugin is referenced in one file (active vs commented)."""

    file: str       # relative path from project root
    active: bool    # True = at least one uncommented reference
    commented: bool # True = at least one commented-out reference


class PackageInfo(BaseModel):
    """CKEditor-relevant fields read from the plugin's package.json (if any)."""

    name: str | None = None
    version: str | None = None
    # Declared '@ckeditor/*' and 'ckeditor5' dependency version specs.
    ckeditor_dependencies: dict[str, str] = {}


class PluginAudit(BaseModel):
    """Full migration report for a single plugin."""

    plugin: str
    status: str          # "migrated" | "not_migrated" | "partial"
    legacy_label: str    # from config (e.g. "v26")
    target_label: str    # from config (e.g. "v47")
    issues: list[Issue]
    used_in_configs: list[ConfigUsage]
    files: list[str]     # all .js files found in the plugin
    package: PackageInfo | None = None  # package.json metadata, if present
    token_savings: TokenSavings


def audit_plugin(name: str) -> PluginAudit:
    """
    Return a detailed migration report for the named CKEditor plugin.

    `name` must be the plugin directory name, e.g. "ckeditor5-box".
    The report includes migration status, all detected legacy pattern hits
    (with file and line), and which config files reference this plugin.
    """
    status = detect_status(name)
    hits = find_pattern_hits(name)
    configs, n_config_files = configs_using(name)
    proot = plugin_root(name)
    source_files = plugin_files(name)
    rel_files = [str(p.relative_to(proot)) for p in source_files]

    issues = [
        Issue(
            file=hit.file,
            line=hit.line,
            legacy=hit.matched,
            replacement=hit.pattern.replacement,
            description=hit.pattern.description,
            category=hit.pattern.category,
        )
        for hit in hits
    ]

    pkg_info = plugin_package_info(name)
    package = PackageInfo(**pkg_info) if pkg_info else None

    n_source = len(source_files)
    files_scanned = n_source + n_config_files
    estimated_saved = n_source * TOKENS_PER_SOURCE_FILE + n_config_files * TOKENS_PER_CONFIG_FILE

    return PluginAudit(
        plugin=name,
        status=status,
        legacy_label=settings.legacy_label,
        target_label=settings.target_label,
        issues=issues,
        used_in_configs=[
            ConfigUsage(file=u.file, active=u.active, commented=u.commented)
            for u in configs
        ],
        files=rel_files,
        package=package,
        token_savings=TokenSavings(
            files_scanned=files_scanned,
            estimated_tokens_saved=estimated_saved,
            note=(
                f"scanned {n_source} source file(s) and {n_config_files} config file(s) "
                f"instead of Claude reading them directly"
            ),
        ),
    )