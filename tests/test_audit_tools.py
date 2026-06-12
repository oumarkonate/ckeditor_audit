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


def test_export_audit_report_markdown(project_root):
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    result = export_audit_report(format="markdown")
    assert result.format == "markdown"
    assert "# CKEditor Migration Audit Report" in result.content
    assert result.plugins_total >= 3
    assert result.output_path is None


def test_export_audit_report_json(project_root):
    import json
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    result = export_audit_report(format="json")
    data = json.loads(result.content)
    assert "summary" in data
    assert "plugins" in data
    assert data["summary"]["total"] >= 3


def test_export_audit_report_write(project_root, tmp_path):
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    out = "audit_report.md"
    result = export_audit_report(format="markdown", output_path=out)
    assert result.output_path is not None
    from pathlib import Path
    assert Path(result.output_path).exists()
