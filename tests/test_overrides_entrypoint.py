"""
Tests for the project overrides (.ckeditor-audit.json) and entrypoint cross-check.

The `settings` singleton is frozen and loaded once at import, so each test builds a
modified copy with `dataclasses.replace` and monkeypatches it onto the scanner module
(the single source of truth read by load_overrides / parse_entrypoint / detect_status).
The lru_cache on load_overrides is cleared on every apply and at teardown.
"""

import dataclasses
import json

import pytest


@pytest.fixture
def apply_overrides(monkeypatch, project_root):
    """Return a helper that installs overrides and/or an entrypoint for one test."""
    # Imported here (not at module top) so the env-setting autouse fixture has
    # already run before config._load() executes.
    from ckeditor_audit.config import settings as base_settings
    from ckeditor_audit.lib import scanner

    created = []

    def _apply(overrides=None, entrypoint=None):
        ovr_file = None
        if overrides is not None:
            ovr_file = project_root / ".ckeditor-audit.json.test"
            raw = overrides if isinstance(overrides, str) else json.dumps(overrides)
            ovr_file.write_text(raw, encoding="utf-8")
            created.append(ovr_file)
        new = dataclasses.replace(
            base_settings, overrides_file=ovr_file, entrypoint=entrypoint
        )
        monkeypatch.setattr(scanner, "settings", new)
        scanner.invalidate_caches()
        return new

    yield _apply

    scanner.invalidate_caches()
    for f in created:
        f.unlink(missing_ok=True)


def _statuses(report):
    return {p.plugin: p.status for p in report.plugins}


# ── Feature 1 / 3 : overrides + to_delete ──────────────────────────────────

def test_to_delete_counted_and_excluded_from_progress(apply_overrides):
    apply_overrides(overrides={"plugins": {"ckeditor5-empty": {
        "status": "to_delete", "reason": "Doublon natif"}}})
    from ckeditor_audit.tools.audit_all import audit_all
    from ckeditor_audit.tools.export_audit_report import export_audit_report

    report = audit_all()
    assert report.to_delete == 1
    assert _statuses(report)["ckeditor5-empty"] == "to_delete"

    data = json.loads(export_audit_report(format="json").content)
    assert data["summary"]["progress"]["to_delete"] == 1
    # countable denominator drops the to_delete plugin
    assert data["summary"]["progress"]["countable"] == report.total - 1

    md = export_audit_report(format="markdown").content
    assert "🗑️ À supprimer" in md
    assert "Doublon natif" in md


def test_aliased_to_leaves_not_migrated(apply_overrides):
    apply_overrides(overrides={"plugins": {"ckeditor5-image": {
        "status": "aliased_to", "aliased_to": "ckeditor5-box",
        "reason": "Renommé"}}})
    from ckeditor_audit.tools.audit_all import audit_all
    from ckeditor_audit.tools.export_audit_report import export_audit_report

    report = audit_all()
    # image was the only not_migrated plugin → now reported as aliased_to
    assert report.not_migrated == 0
    assert report.to_delete == 1
    assert _statuses(report)["ckeditor5-image"] == "aliased_to"

    md_result = export_audit_report(format="markdown")
    assert md_result.plugins_to_delete == 1
    md = md_result.content
    assert "🗑️ À supprimer" in md
    assert "ckeditor5-image" in md
    assert "→ `ckeditor5-box`" in md


def test_requires_reimplementation_subsection(apply_overrides):
    apply_overrides(overrides={"plugins": {"ckeditor5-image": {
        "status": "requires_reimplementation",
        "reason": "API Mention changée",
        "functional_replacement": "Mention from 'ckeditor5'"}}})
    from ckeditor_audit.tools.audit_all import audit_all
    from ckeditor_audit.tools.export_audit_report import export_audit_report

    report = audit_all()
    assert report.requires_reimplementation == 1
    assert report.not_migrated == 0

    md = export_audit_report(format="markdown").content
    assert "♻️ Ré-implémentation requise" in md
    assert "API Mention changée" in md


def test_force_not_migrated_overrides_auto_detection(apply_overrides):
    """A `not_migrated` override forces the status even when code auto-detects as
    migrated (e.g. ported code that is present but not wired up)."""
    apply_overrides(overrides={"plugins": {"ckeditor5-box": {
        "status": "not_migrated",
        "reason": "Porté mais non câblé dans l'entrypoint"}}})
    from ckeditor_audit.tools.audit_all import audit_all
    from ckeditor_audit.tools.audit_plugin import audit_plugin

    report = audit_all()
    statuses = _statuses(report)
    # box auto-detects as migrated; the override flips it to not_migrated.
    assert statuses["ckeditor5-box"] == "not_migrated"
    # image (genuinely not migrated) + box (forced) → 2
    assert report.not_migrated == 2
    # the forced plugin carries no legacy issues (nothing to migrate)
    assert audit_plugin("ckeditor5-box").status == "not_migrated"


def test_skip_excluded_entirely(apply_overrides):
    apply_overrides(overrides={"plugins": {"ckeditor5-empty": {"status": "skip"}}})
    from ckeditor_audit.tools.audit_all import audit_all

    report = audit_all()
    assert "ckeditor5-empty" not in {p.plugin for p in report.plugins}


def test_override_reflected_in_audit_plugin(apply_overrides):
    """Coherence: detect_status drives audit_plugin too."""
    apply_overrides(overrides={"plugins": {"ckeditor5-box": {"status": "to_delete"}}})
    from ckeditor_audit.tools.audit_plugin import audit_plugin

    assert audit_plugin("ckeditor5-box").status == "to_delete"


# ── Robustness : malformed / absent overrides ──────────────────────────────

def test_malformed_overrides_no_crash(apply_overrides):
    from ckeditor_audit.lib import scanner
    apply_overrides(overrides="{ this is : not valid json ")
    assert scanner.load_overrides() == {}


def test_absent_overrides_returns_empty(apply_overrides):
    from ckeditor_audit.lib import scanner
    apply_overrides(overrides=None)
    assert scanner.load_overrides() == {}


# ── Feature 2 : entrypoint cross-check ─────────────────────────────────────

def test_entrypoint_active_vs_commented(apply_overrides, tmp_path):
    ep = tmp_path / "ckeditor.js"
    ep.write_text(
        "// import Box from 'ckeditor5-box';\n"
        "import Image from 'ckeditor5-image';\n",
        encoding="utf-8",
    )
    apply_overrides(entrypoint=ep)

    from ckeditor_audit.lib import scanner
    cross = scanner.parse_entrypoint()
    assert "ckeditor5-image" in cross["active"]
    assert "ckeditor5-box" in cross["commented"]

    from ckeditor_audit.tools.audit_all import audit_all
    activity = {p.plugin: p.entrypoint_active for p in audit_all().plugins}
    assert activity["ckeditor5-image"] is True
    assert activity["ckeditor5-box"] is False


def test_not_migrated_active_is_priority(apply_overrides, tmp_path):
    ep = tmp_path / "ckeditor.js"
    # image is not_migrated AND active in the entrypoint → priority
    ep.write_text("import Image from 'ckeditor5-image';\n", encoding="utf-8")
    apply_overrides(entrypoint=ep)

    from ckeditor_audit.tools.export_audit_report import export_audit_report
    md = export_audit_report(format="markdown").content
    assert "prioritaire" in md


def test_entrypoint_absent_no_marking(apply_overrides):
    from ckeditor_audit.lib import scanner
    apply_overrides()  # no entrypoint configured
    assert scanner.parse_entrypoint() == {"active": set(), "commented": set()}


def test_entrypoint_pascalcase_commented(apply_overrides, tmp_path):
    """builtinPlugins reference plugins by PascalCase, not the folder name."""
    from ckeditor_audit.lib.scanner import parse_entrypoint
    ep = tmp_path / "ckeditor.js"
    ep.write_text(
        "builtinPlugins = [\n  // Box,\n  Image,\n];\n", encoding="utf-8"
    )
    apply_overrides(entrypoint=ep)
    cross = parse_entrypoint()
    assert "ckeditor5-box" in cross["commented"]
    assert "ckeditor5-image" in cross["active"]


# ── Multi-term matching (pure helpers) ─────────────────────────────────────

def test_search_terms_generation():
    from ckeditor_audit.lib.scanner import _search_terms
    assert _search_terms("ckeditor5-wordcount") == [
        "ckeditor5-wordcount", "Wordcount", "WORDCOUNT", "wordcount"]
    assert _search_terms("ckeditor5-media-embed") == [
        "ckeditor5-media-embed", "MediaEmbed",
        "MEDIA_EMBED", "media-embed"]


def test_word_boundary_matching():
    from ckeditor_audit.lib.scanner import _plugin_in_line
    # no false positive on substrings
    assert _plugin_in_line("ckeditor5-box", "import x from './toolbox';") is False
    assert _plugin_in_line("ckeditor5-box", "const x = ckeditor5Box;") is False
    # real references match
    assert _plugin_in_line("ckeditor5-box", "import B from 'ckeditor5-box';") is True
    assert _plugin_in_line("ckeditor5-box", "  // Box,") is True
    # SCREAMING_SNAKE from a hyphenated name matches a PHP/YAML constant
    assert _plugin_in_line(
        "ckeditor5-media-embed", "// self::PLUGIN_MEDIA_EMBED,") is True


# ── config_files scanning ──────────────────────────────────────────────────

def test_config_files_active_and_commented(apply_overrides, project_root):
    import shutil
    from ckeditor_audit.lib.scanner import configs_using
    d = project_root / "cfgtest"
    d.mkdir(exist_ok=True)
    try:
        (d / "plugins.js").write_text(
            "export const BOX_PLUGIN = 'Box';\n", encoding="utf-8")
        (d / "Type.php").write_text(
            "<?php\n// self::PLUGIN_BOX,\n", encoding="utf-8")
        apply_overrides(overrides={"config_files": [
            "cfgtest/plugins.js", "cfgtest/Type.php"]})
        usages, _ = configs_using("ckeditor5-box")
        byfile = {u.file: u for u in usages}
        assert byfile["cfgtest/plugins.js"].active is True
        assert byfile["cfgtest/Type.php"].commented is True
        assert byfile["cfgtest/Type.php"].active is False
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_config_files_absent_or_malformed(apply_overrides):
    from ckeditor_audit.lib.scanner import load_config_files
    apply_overrides(overrides=None)
    assert load_config_files() == []
    apply_overrides(overrides="{ broken json ")
    assert load_config_files() == []
    apply_overrides(overrides={"plugins": {}})  # no config_files key
    assert load_config_files() == []


def test_config_files_nonexistent_path_skipped(apply_overrides):
    """A declared config file that does not exist is skipped, never crashes."""
    from ckeditor_audit.lib.scanner import configs_using, load_config_files
    apply_overrides(overrides={"config_files": ["does/not/exist.js"]})
    # the path is loaded but filtered out by the is_file() guard in configs_using
    assert len(load_config_files()) == 1
    usages, _ = configs_using("ckeditor5-image")  # must not raise
    # existing glob results are unaffected (image still commented there)
    assert any(u.commented for u in usages)
