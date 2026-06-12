"""
Tool: export_audit_report

Generate a full Markdown or JSON audit report covering all plugins.
Returns the content as a string by default (read-only).
Writes to a file only if output_path is explicitly provided.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from ckeditor_audit.config import settings
from ckeditor_audit.lib.patterns import PATTERNS
from ckeditor_audit.lib.scanner import (
    configs_using,
    detect_status,
    find_pattern_hits,
    list_plugins,
    plugin_files,
    plugin_root,
)
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


def _git_info(root: Path) -> dict:
    """Gather git metadata. Returns empty dict if not a git repo or git unavailable."""
    def _run(*args):
        r = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None

    try:
        branch = _run("rev-parse", "--abbrev-ref", "HEAD")
        if branch is None:
            return {}
        log_line = _run("log", "-1", "--pretty=%h|%ai|%s")
        commit_hash = commit_date = commit_message = None
        if log_line:
            parts = log_line.split("|", 2)
            if len(parts) == 3:
                commit_hash, commit_date, commit_message = parts
        remote = _run("config", "--get", "remote.origin.url")
        return {
            "branch": branch,
            "commit_hash": commit_hash,
            "commit_date": commit_date,
            "commit_message": commit_message,
            "remote": remote,
        }
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}


def _progress_bar(done: int, total: int, width: int = 20) -> str:
    """Return e.g. '[████████░░░░] 67 %'"""
    if total == 0:
        filled, pct = 0, 0
    else:
        filled = round(width * done / total)
        pct = round(100 * done / total)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct} %"


def _collect_stats(rows: list[dict]) -> dict:
    """Compute aggregate stats from pre-collected plugin rows."""
    total_files = sum(r["file_count"] for r in rows)
    total_issues = sum(len(r["hits"]) for r in rows)
    issues_by_category: dict[str, int] = {}
    for r in rows:
        for h in r["hits"]:
            cat = h.pattern.category
            issues_by_category[cat] = issues_by_category.get(cat, 0) + 1
    configs_active = sum(
        1 for r in rows if any(u.active for u in r["config_usages"])
    )
    configs_scanned = sum(len(r["config_usages"]) for r in rows)
    return {
        "total_source_files": total_files,
        "total_issues": total_issues,
        "issues_by_category": issues_by_category,
        "configs_scanned": configs_scanned,
        "plugins_with_active_config": configs_active,
        "known_patterns": len(PATTERNS),
    }


def _complexity(hit_count: int) -> tuple[str, str]:
    """Return (level, icon) based on number of issues."""
    if hit_count <= 3:
        return ("simple", "🟢")
    if hit_count <= 9:
        return ("medium", "🟡")
    return ("complex", "🔴")


def _issues_table(hits: list, lines: list) -> None:
    """Append category-grouped issue tables to lines (mutates in place)."""
    by_cat: dict[str, list] = {}
    for h in hits:
        by_cat.setdefault(h.pattern.category, []).append(h)
    for cat, cat_hits in sorted(by_cat.items()):
        lines += [
            f"**{cat}** ({len(cat_hits)} issue(s))",
            "",
            "| Fichier | Ligne | Legacy | Remplacement |",
            "|---------|-------|--------|--------------|",
        ]
        for h in cat_hits:
            legacy_short = h.pattern.legacy[:60].replace("|", "\\|")
            repl_short = h.pattern.replacement[:60].replace("|", "\\|")
            lines.append(
                f"| `{h.file}` | {h.line} | `{legacy_short}` | `{repl_short}` |"
            )
        lines.append("")


def export_audit_report(
    format: str = "markdown",
    output_path: str | None = None,
) -> ExportAuditReportResult:
    """
    Generate a full audit report for all CKEditor plugins.

    Produces a Markdown or JSON report with:
    - Rich summary: git info, progress bar with %, detailed stats
    - Plugins grouped by status: not_migrated (sub-grouped by complexity) → partial → migrated
    - not_migrated plugins sub-grouped by complexity (simple / medium / complex)
    - Partial plugins include a todo list (already-migrated files vs remaining issues)

    Args:
        format: Output format — "markdown" (default) or "json".
        output_path: Optional path (relative to project_root) to write the report.
                     If omitted, the report is returned as a string only.
    """
    root = settings.project_root
    plugins = list_plugins()
    rows: list[dict] = []
    for name in plugins:
        status = detect_status(name)
        hits = find_pattern_hits(name)
        config_usages, _ = configs_using(name)
        pfiles = plugin_files(name)
        pr = plugin_root(name)
        modern_files = [
            str(p.relative_to(pr))
            for p in pfiles
            if "from 'ckeditor5'" in p.read_text(encoding="utf-8", errors="ignore")
        ]
        rows.append({
            "name": name,
            "status": status,
            "hits": hits,
            "file_count": len(pfiles),
            "config_usages": config_usages,
            "modern_files": modern_files,
        })

    migrated = sum(1 for r in rows if r["status"] == "migrated")
    partial = sum(1 for r in rows if r["status"] == "partial")
    not_migrated_count = sum(1 for r in rows if r["status"] == "not_migrated")
    total = len(plugins)
    pct = round(100 * migrated / total) if total else 0

    git = _git_info(root)
    stats = _collect_stats(rows)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    nm_rows = sorted(
        [r for r in rows if r["status"] == "not_migrated"],
        key=lambda r: len(r["hits"]),
    )
    partial_rows = [r for r in rows if r["status"] == "partial"]
    migrated_rows = [r for r in rows if r["status"] == "migrated"]

    # ── Build Markdown (always, used for auto-save and for format="markdown") ──
    estimated_tokens_saved = total * 800
    pct_partial = round(100 * partial / total) if total else 0
    pct_nm = round(100 * not_migrated_count / total) if total else 0

    md_lines = [
        "# CKEditor Migration Audit Report",
        "",
        "## Summary",
        "",
        f"**Projet** : `{root}`  |  "
        f"Migration : {settings.legacy_label} → {settings.target_label}  |  "
        f"Généré le : {generated_at}",
        "",
    ]

    if git:
        md_lines += ["### Git", ""]
        md_lines.append(f"- **Branche** : `{git.get('branch', '?')}`")
        if git.get("commit_hash"):
            md_lines.append(
                f"- **Dernier commit** : `{git['commit_hash']}` — "
                f"{git.get('commit_date', '?')} — \"{git.get('commit_message', '')}\""
            )
        if git.get("remote"):
            md_lines.append(f"- **Remote** : `{git['remote']}`")
        md_lines.append("")

    md_lines += [
        "### Avancement",
        "",
        _progress_bar(migrated, total),
        "",
        "| Statut | Plugins | % |",
        "|--------|---------|---|",
        f"| ✅ Migrés | {migrated} | {pct} % |",
        f"| ⚠️ Partiels | {partial} | {pct_partial} % |",
        f"| ❌ Non migrés | {not_migrated_count} | {pct_nm} % |",
        f"| **Total** | **{total}** | |",
        "",
        "### Statistiques",
        "",
        "| Métrique | Valeur |",
        "|----------|--------|",
        f"| Fichiers source JS | {stats['total_source_files']} |",
        f"| Issues legacy totales | {stats['total_issues']} |",
    ]
    for cat, cnt in sorted(stats["issues_by_category"].items()):
        md_lines.append(f"| &nbsp;&nbsp;dont {cat} | {cnt} |")
    md_lines += [
        f"| Fichiers de config scannés | {stats['configs_scanned']} |",
        f"| Plugins avec config active | {stats['plugins_with_active_config']} |",
        f"| Patterns connus | {stats['known_patterns']} |",
        f"| Tokens économisés (estimé) | ~{estimated_tokens_saved:,} |",
        "",
        "---",
        "",
    ]

    # ── not_migrated, sub-grouped by complexity ──
    if nm_rows:
        md_lines += [f"## ❌ Non migrés ({len(nm_rows)} plugins)", ""]

        complexity_order = [("simple", "🟢"), ("medium", "🟡"), ("complex", "🔴")]
        complexity_labels = {
            "simple": "Simples (1–3 issues)",
            "medium": "Moyens (4–9 issues)",
            "complex": "Complexes (10+ issues)",
        }
        groups_by_complexity: dict[str, list] = {}
        for r in nm_rows:
            level, _ = _complexity(len(r["hits"]))
            groups_by_complexity.setdefault(level, []).append(r)

        for level, icon in complexity_order:
            grp = groups_by_complexity.get(level)
            if not grp:
                continue
            label = complexity_labels[level]
            md_lines += [f"### {icon} {label} — {len(grp)} plugin(s)", ""]
            for r in grp:
                active_c = sum(1 for u in r["config_usages"] if u.active)
                commented_c = sum(1 for u in r["config_usages"] if u.commented)
                md_lines += [
                    f"#### `{r['name']}` — {len(r['hits'])} issue(s)",
                    "",
                    f"- **Fichiers JS** : {r['file_count']}  |  "
                    f"**Configs** : {active_c} active, {commented_c} commentée",
                    "",
                ]
                _issues_table(r["hits"], md_lines)
                md_lines += [
                    f"> Lancez `/ckeditor-migrate {r['name']}` pour appliquer ces corrections.",
                    "",
                ]
        md_lines += ["---", ""]

    # ── partial ──
    if partial_rows:
        md_lines += [f"## ⚠️ Partiels ({len(partial_rows)} plugins)", ""]
        for r in partial_rows:
            active_c = sum(1 for u in r["config_usages"] if u.active)
            commented_c = sum(1 for u in r["config_usages"] if u.commented)
            md_lines += [
                f"### ⚠️ `{r['name']}` — partial (migration en cours)",
                "",
                f"- **Fichiers JS** : {r['file_count']}  |  "
                f"**Configs** : {active_c} active, {commented_c} commentée",
                "",
            ]
            if r["modern_files"]:
                md_lines += ["#### ✅ Déjà migré (imports modernes détectés)", ""]
                for mf in r["modern_files"]:
                    md_lines.append(f"- `{mf}`")
                md_lines.append("")
            if r["hits"]:
                md_lines += [f"#### ❌ Reste à migrer — {len(r['hits'])} issue(s)", ""]
                _issues_table(r["hits"], md_lines)
                md_lines += [
                    f"> Lancez `/ckeditor-migrate {r['name']}` pour appliquer ces corrections.",
                    "",
                ]
        md_lines += ["---", ""]

    # ── migrated ──
    if migrated_rows:
        md_lines += [f"## ✅ Migrés ({len(migrated_rows)} plugins)", ""]
        for r in migrated_rows:
            md_lines.append(f"- ✅ `{r['name']}` — aucun pattern legacy détecté")
        md_lines.append("")

    md_content = "\n".join(md_lines)

    # ── Build JSON if requested ──
    if format == "json":
        def _plugin_json(r: dict) -> dict:
            entry: dict = {
                "name": r["name"],
                "status": r["status"],
                "file_count": r["file_count"],
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
            if r["status"] == "not_migrated":
                level, _ = _complexity(len(r["hits"]))
                entry["complexity"] = level
            if r["status"] == "partial":
                entry["modern_files"] = r["modern_files"]
            return entry

        data = {
            "summary": {
                "generated_at": generated_at,
                "project_root": str(root),
                "migration": {"from": settings.legacy_label, "to": settings.target_label},
                "progress": {
                    "migrated": migrated,
                    "partial": partial,
                    "not_migrated": not_migrated_count,
                    "total": total,
                    "percent": pct,
                },
                "stats": stats,
                "git": git,
                "token_savings": {
                    "estimated_tokens_saved": estimated_tokens_saved,
                    "note": (
                        f"audited {total} plugin(s): "
                        f"{migrated} migrated, {partial} partial, {not_migrated_count} not_migrated"
                    ),
                },
            },
            "groups": {
                "not_migrated": [_plugin_json(r) for r in nm_rows],
                "partial": [_plugin_json(r) for r in partial_rows],
                "migrated": [_plugin_json(r) for r in migrated_rows],
            },
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        content = md_content

    # ── Always persist Markdown to tmp/ ──
    auto_md_path = settings.project_root / "tmp" / "ckeditor-audit-report.md"
    auto_md_path.parent.mkdir(parents=True, exist_ok=True)
    auto_md_path.write_text(md_content, encoding="utf-8")

    written_path = str(auto_md_path)
    if output_path:
        full_path = settings.project_root / output_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        written_path = str(full_path)

    return ExportAuditReportResult(
        format=format,
        content=content,
        plugins_total=total,
        plugins_migrated=migrated,
        plugins_partial=partial,
        plugins_not_migrated=not_migrated_count,
        output_path=written_path,
        token_savings=TokenSavings(
            files_scanned=total,
            estimated_tokens_saved=total * 800,
            note=(
                f"audited {total} plugin(s): "
                f"{migrated} migrated, {partial} partial, {not_migrated_count} not_migrated"
            ),
        ),
    )
