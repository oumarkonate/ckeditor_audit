"""Tests for CKEditor-specific audit tools."""

import pytest


def test_list_patterns():
    from ckeditor_audit.tools.list_patterns import list_patterns
    result = list_patterns()
    assert len(result) > 0
    # All patterns have required fields
    for p in result:
        assert p.legacy
        assert p.replacement
        assert p.category in ("import", "api", "schema", "utils")


def test_audit_all(project_root):
    from ckeditor_audit.tools.audit_all import audit_all
    result = audit_all()
    assert result.total >= 3
    assert result.migrated >= 1
    assert result.partial >= 1
    assert result.not_migrated >= 1
    assert result.token_savings.files_scanned >= 3


def test_audit_plugin_migrated(project_root):
    from ckeditor_audit.tools.audit_plugin import audit_plugin
    result = audit_plugin("ckeditor5-box")
    assert result.plugin == "ckeditor5-box"
    assert result.status == "migrated"
    assert result.issues == []


def test_audit_plugin_not_migrated(project_root):
    from ckeditor_audit.tools.audit_plugin import audit_plugin
    result = audit_plugin("ckeditor5-image")
    assert result.plugin == "ckeditor5-image"
    assert result.status == "not_migrated"
    assert len(result.issues) > 0


def test_find_plugin_usages(project_root):
    from ckeditor_audit.tools.find_plugin_usages import find_plugin_usages
    result = find_plugin_usages("ckeditor5-box")
    assert len(result.usages) == 1
    assert result.usages[0].active is True


def test_find_plugin_usages_commented(project_root):
    from ckeditor_audit.tools.find_plugin_usages import find_plugin_usages
    result = find_plugin_usages("ckeditor5-image")
    assert len(result.usages) == 1
    assert result.usages[0].commented is True


def test_suggest_migration(project_root):
    from ckeditor_audit.tools.suggest_migration import suggest_migration
    result = suggest_migration("ckeditor5-image")
    assert result.plugin == "ckeditor5-image"
    assert result.total_fixes > 0
    # Each fix has all required fields
    for fix in result.fixes:
        assert fix.file
        assert fix.line > 0
        assert fix.legacy
        assert fix.replacement
        assert fix.category


def test_validate_migration_clean(project_root):
    from ckeditor_audit.tools.validate_migration import validate_migration
    result = validate_migration("ckeditor5-box")
    assert result.plugin == "ckeditor5-box"
    assert result.status == "migrated"
    assert result.clean is True
    assert result.remaining_hits == []


def test_validate_migration_dirty(project_root):
    from ckeditor_audit.tools.validate_migration import validate_migration
    result = validate_migration("ckeditor5-image")
    assert result.clean is False
    assert len(result.remaining_hits) > 0
    assert result.remaining_hits[0].line > 0


def test_invariant_not_migrated_implies_fixes(project_root):
    """Core invariant: any plugin flagged not_migrated/partial yields >=1 hit.

    This guards the historical bug where a plugin could be detected as needing
    migration yet suggest_migration returned an empty list (deep import absent
    from the hardcoded catalog).
    """
    from ckeditor_audit.lib.scanner import (
        detect_status,
        find_pattern_hits,
        list_plugins,
    )
    for name in list_plugins():
        status = detect_status(name)
        if status in ("not_migrated", "partial"):
            assert len(find_pattern_hits(name)) > 0, f"{name} ({status}) yielded no hits"


def test_partial_plugin_generic_fallback(project_root):
    """The partial 'toolbar' plugin uses a deep import absent from the catalog;
    the generic fallback rule must still surface an actionable fix that reports
    the actual import verbatim (not a regex/placeholder)."""
    from ckeditor_audit.tools.suggest_migration import suggest_migration
    result = suggest_migration("ckeditor5-toolbar")
    assert result.total_fixes > 0
    assert any(
        "@ckeditor/ckeditor5-ui/src/toolbar/toolbar" in fix.legacy
        for fix in result.fixes
    )


def test_regex_pattern_matches_whitespace(project_root):
    """is_regex schema pattern (allowIn:\\s*'root') matches the spaced variant."""
    from ckeditor_audit.lib.scanner import find_pattern_hits
    hits = find_pattern_hits("ckeditor5-image")
    assert any(h.pattern.category == "schema" for h in hits)


def test_no_imports_status(project_root):
    """A plugin with no CKEditor imports is reported as 'no_imports', not
    'not_migrated', and has no issues."""
    from ckeditor_audit.tools.audit_plugin import audit_plugin
    result = audit_plugin("ckeditor5-empty")
    assert result.status == "no_imports"
    assert result.issues == []


def test_patterns_loaded_from_json(project_root):
    """The catalog is loaded from the JSON data file and includes regex entries."""
    from ckeditor_audit.lib.patterns import PATTERNS
    assert len(PATTERNS) >= 14
    assert any(p.is_regex for p in PATTERNS)


def test_export_audit_report_markdown(project_root):
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    from pathlib import Path
    result = export_audit_report(format="markdown")
    assert result.format == "markdown"
    assert "# CKEditor Migration Audit Report" in result.content
    assert result.plugins_total >= 3
    # Report is always auto-saved to tmp/ckeditor-audit-report.md
    assert result.output_path is not None
    assert Path(result.output_path).exists()


def test_export_audit_report_json(project_root):
    import json
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    result = export_audit_report(format="json")
    data = json.loads(result.content)
    assert "summary" in data
    assert "groups" in data
    assert data["summary"]["progress"]["total"] >= 3
    assert "not_migrated" in data["groups"]
    assert "partial" in data["groups"]
    assert "migrated" in data["groups"]
    # not_migrated entries have complexity field
    for entry in data["groups"]["not_migrated"]:
        assert entry["complexity"] in ("simple", "medium", "complex")


def test_export_audit_report_write(project_root, tmp_path):
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    out = "audit_report.md"
    result = export_audit_report(format="markdown", output_path=out)
    assert result.output_path is not None
    from pathlib import Path
    assert Path(result.output_path).exists()
