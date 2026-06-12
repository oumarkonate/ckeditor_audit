"""
Tool: export_audit_report

Generate a full Markdown or JSON audit report covering all plugins.
Returns the content as a string by default (read-only).
Writes to a file only if output_path is explicitly provided.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.scanner import detect_status, find_pattern_hits, list_plugins
from ckeditor_audit.tools.common import TokenSavings


class ExportAuditReportResult(BaseModel):
    format: str
    content: str
    plugins_total: int
    plugins_migrated: int
    plugins_partial: int
    plugins_not_migrated: int
    output_path: str | None
    token_savings: TokenSavings


def export_audit_report(
    format: str = "markdown",
    output_path: str | None = None,
) -> ExportAuditReportResult:
    """
    Generate a full audit report for all CKEditor plugins.

    Produces a Markdown or JSON report with:
    - Migration status summary (migrated / partial / not_migrated counts)
    - Per-plugin detail with all detected legacy pattern hits
    - File and line references for each issue

    Args:
        format: Output format — "markdown" (default) or "json".
        output_path: Optional path (relative to project_root) to write the report.
                     If omitted, the report is returned as a string only.

    Returns the report content as a string.
    """
    plugins = list_plugins()
    rows = []
    for name in plugins:
        status = detect_status(name)
        hits = find_pattern_hits(name)
        rows.append({"name": name, "status": status, "hits": hits})

    migrated = sum(1 for r in rows if r["status"] == "migrated")
    partial = sum(1 for r in rows if r["status"] == "partial")
    not_migrated = sum(1 for r in rows if r["status"] == "not_migrated")

    if format == "json":
        data = {
            "summary": {
                "total": len(plugins),
                "migrated": migrated,
                "partial": partial,
                "not_migrated": not_migrated,
            },
            "plugins": [
                {
                    "name": r["name"],
                    "status": r["status"],
                    "hits": [
                        {
                            "file": h.file,
                            "line": h.line,
                            "category": h.pattern.category,
                            "legacy": h.pattern.legacy,
                            "replacement": h.pattern.replacement,
                        }
                        for h in r["hits"]
                    ],
                }
                for r in rows
            ],
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        lines = [
            "# CKEditor Migration Audit Report",
            "",
            "## Summary",
            "",
            f"| Status | Count |",
            f"|--------|-------|",
            f"| Migrated | {migrated} |",
            f"| Partial | {partial} |",
            f"| Not migrated | {not_migrated} |",
            f"| **Total** | **{len(plugins)}** |",
            "",
            "---",
            "",
            "## Plugins",
            "",
        ]
        STATUS_ICON = {"migrated": "✅", "partial": "⚠️", "not_migrated": "❌"}
        for r in rows:
            icon = STATUS_ICON.get(r["status"], "?")
            lines.append(f"### {icon} `{r['name']}` — {r['status']}")
            lines.append("")
            if r["hits"]:
                lines.append("| File | Line | Category | Legacy pattern |")
                lines.append("|------|------|----------|----------------|")
                for h in r["hits"]:
                    legacy_short = h.pattern.legacy[:60].replace("|", "\\|")
                    lines.append(
                        f"| `{h.file}` | {h.line} | {h.pattern.category} | `{legacy_short}` |"
                    )
                lines.append("")
                lines.append("**Replacements needed:**")
                lines.append("")
                seen = set()
                for h in r["hits"]:
                    key = h.pattern.legacy
                    if key not in seen:
                        seen.add(key)
                        lines.append(f"- **{h.pattern.category}**: `{h.pattern.legacy}`")
                        lines.append(f"  → `{h.pattern.replacement}`")
                        lines.append(f"  _{h.pattern.description}_")
            else:
                lines.append("_No legacy patterns detected._")
            lines.append("")
            lines.append("---")
            lines.append("")
        content = "\n".join(lines)

    written_path = None
    if output_path:
        full_path = settings.project_root / output_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        written_path = str(full_path)

    return ExportAuditReportResult(
        format=format,
        content=content,
        plugins_total=len(plugins),
        plugins_migrated=migrated,
        plugins_partial=partial,
        plugins_not_migrated=not_migrated,
        output_path=written_path,
        token_savings=TokenSavings(
            files_scanned=len(plugins),
            estimated_tokens_saved=len(plugins) * 800,
            note=(
                f"audited {len(plugins)} plugin(s): "
                f"{migrated} migrated, {partial} partial, {not_migrated} not_migrated"
            ),
        ),
    )
