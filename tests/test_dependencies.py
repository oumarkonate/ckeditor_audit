"""Tests for the package.json version audit and audit_dependencies tool."""


def test_audit_plugin_package_info(project_root):
    from ckeditor_audit.tools.audit_plugin import audit_plugin
    result = audit_plugin("ckeditor5-image")
    assert result.package is not None
    assert result.package.version == "1.2.3"
    assert "@ckeditor/ckeditor5-core" in result.package.ckeditor_dependencies


def test_audit_plugin_no_package(project_root):
    """toolbar has no package.json — package is None, not an error."""
    from ckeditor_audit.tools.audit_plugin import audit_plugin
    result = audit_plugin("ckeditor5-toolbar")
    assert result.package is None


def test_audit_dependencies(project_root):
    from ckeditor_audit.tools.audit_dependencies import audit_dependencies
    result = audit_dependencies()
    assert result.manifests_scanned >= 2
    # legacy @ckeditor/* packages from image's manifest
    assert result.legacy_packages >= 2
    # modern flat package from box's manifest
    assert result.modern_packages >= 1
    pkgs = {d.package for d in result.dependencies}
    assert "@ckeditor/ckeditor5-core" in pkgs
    assert "ckeditor5" in pkgs
    core = next(d for d in result.dependencies if d.package == "@ckeditor/ckeditor5-core")
    assert core.legacy is True
    assert "^41.0.0" in core.versions
