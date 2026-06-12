"""Tests for generic search tools (ported from project_search)."""

import pytest


def test_find_files(project_root):
    from ckeditor_audit.tools.find_files import find_files
    result = find_files(pattern="box")
    assert len(result.results) > 0
    assert any("box.js" in f.path for f in result.results)


def test_grep_code(project_root):
    from ckeditor_audit.tools.grep_code import grep_code
    # Default output="compact" → matches=None, compact is populated
    result = grep_code(query="ckeditor5-core", output="compact")
    assert result.token_savings.files_scanned > 0
    assert "image.js" in result.compact


def test_grep_code_no_match(project_root):
    from ckeditor_audit.tools.grep_code import grep_code
    result = grep_code(query="THIS_PATTERN_DOES_NOT_EXIST_XYZ_9999")
    assert (result.matches or []) == []


def test_grep_with_context(project_root):
    from ckeditor_audit.tools.grep_with_context import grep_with_context
    result = grep_with_context(query="Plugin", context_lines=1)
    assert len(result.matches) > 0
    first = result.matches[0]
    assert "before" in first.__dict__ or hasattr(first, "before")


def test_count_matches(project_root):
    from ckeditor_audit.tools.count_matches import count_matches
    result = count_matches(query="import")
    assert result.total_matches > 0
    assert result.files_matched > 0


def test_read_file(project_root):
    from ckeditor_audit.tools.read_file import read_file
    result = read_file(path="assets/ckeditor/ckeditor5-box/src/box.js")
    assert "Plugin" in result.content
    assert result.total_lines > 0


def test_directory_tree(project_root):
    from ckeditor_audit.tools.directory_tree import directory_tree
    result = directory_tree(directory="assets/ckeditor")
    assert "ckeditor5-box" in result.tree


def test_git_changed_files(project_root):
    from ckeditor_audit.tools.git_changed_files import git_changed_files
    # Raises RuntimeError if project_root is not a git repo — catch gracefully
    try:
        result = git_changed_files(scope="unstaged")
        assert isinstance(result.files, list)
    except RuntimeError as e:
        assert "git" in str(e).lower()


def test_grep_changed_reexport(project_root):
    """grep_changed is re-exported from searcher after the git_ops extraction;
    on a non-git fixture it returns gracefully or raises a git RuntimeError."""
    from ckeditor_audit.lib.searcher import grep_changed
    try:
        results, n = grep_changed("Plugin")
        assert isinstance(results, list)
    except RuntimeError as e:
        assert "git" in str(e).lower()


def test_grep_code_with_extension_filter(project_root):
    from ckeditor_audit.tools.grep_code import grep_code
    result = grep_code(query="import", extensions=["js"], output="compact")
    assert result.token_savings.files_scanned > 0
    assert result.compact  # non-empty compact output
    # All lines reference .js files
    for line in result.compact.splitlines():
        assert ".js:" in line


def test_find_class(project_root):
    from ckeditor_audit.tools.find_class import find_class
    result = find_class(class_name="Box")
    # Returns results (ast-grep or regex fallback); field is "results"
    assert hasattr(result, "results")


def test_get_file_outline(project_root):
    from ckeditor_audit.tools.get_file_outline import get_file_outline
    result = get_file_outline(path="assets/ckeditor/ckeditor5-box/src/box.js")
    assert hasattr(result, "results")
