"""
Tool: audit_dependencies

Project-wide, read-only view of remaining CKEditor dependencies.

Scans every package.json (outside excluded dirs) for '@ckeditor/*' and
'ckeditor5' entries and aggregates them, giving a macro picture of how far the
migration to the flat 'ckeditor5' package has progressed.
"""

import json

from pydantic import BaseModel

from ckeditor_audit.lib.constants import TOKENS_PER_CONFIG_FILE
from ckeditor_audit.lib.scanner import _ckeditor_deps, find_package_jsons
from ckeditor_audit.config import settings
from ckeditor_audit.tools.common import TokenSavings


class DependencyUsage(BaseModel):
    """One CKEditor dependency and where it is declared."""

    package: str                 # e.g. "@ckeditor/ckeditor5-core" or "ckeditor5"
    legacy: bool                 # True for any "@ckeditor/*" scoped package
    versions: list[str]          # distinct version specs seen across manifests
    declared_in: list[str]       # package.json paths (relative to project root)


class AuditDependenciesReport(BaseModel):
    manifests_scanned: int
    legacy_packages: int         # count of distinct "@ckeditor/*" packages still declared
    modern_packages: int         # 1 if "ckeditor5" is declared anywhere, else 0
    dependencies: list[DependencyUsage]
    token_savings: TokenSavings


def audit_dependencies() -> AuditDependenciesReport:
    """
    Audit CKEditor dependencies declared across all package.json files.

    Returns every '@ckeditor/*' (legacy) and 'ckeditor5' (modern) dependency
    still declared in the project, the version spec(s) seen, and which manifests
    declare them. Use it for a macro view of migration progress, complementing
    the per-plugin source audit from `audit_all`.
    """
    root = settings.project_root
    manifests = find_package_jsons()

    # package -> {"versions": set, "files": set}
    agg: dict[str, dict] = {}
    for pkg_path in manifests:
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, ValueError):
            continue
        rel = str(pkg_path.relative_to(root))
        for pkg, ver in _ckeditor_deps(data).items():
            entry = agg.setdefault(pkg, {"versions": set(), "files": set()})
            entry["versions"].add(ver)
            entry["files"].add(rel)

    dependencies = [
        DependencyUsage(
            package=pkg,
            legacy=pkg.startswith("@ckeditor/"),
            versions=sorted(entry["versions"]),
            declared_in=sorted(entry["files"]),
        )
        for pkg, entry in sorted(agg.items())
    ]

    legacy_packages = sum(1 for d in dependencies if d.legacy)
    modern_packages = sum(1 for d in dependencies if not d.legacy)

    n = len(manifests)
    return AuditDependenciesReport(
        manifests_scanned=n,
        legacy_packages=legacy_packages,
        modern_packages=modern_packages,
        dependencies=dependencies,
        token_savings=TokenSavings(
            files_scanned=n,
            estimated_tokens_saved=n * TOKENS_PER_CONFIG_FILE,
            note=(
                f"scanned {n} package.json file(s): {legacy_packages} legacy "
                f"'@ckeditor/*' package(s) still declared"
            ),
        ),
    )
