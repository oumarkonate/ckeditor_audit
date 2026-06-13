"""Tests for code-intelligence and navigation tools.

These exercise the search tools that were previously uncovered, using the PHP
controller and JS module added to the fixture project in conftest.py.
"""

import pytest

try:
    import ast_grep_py  # noqa: F401
    _AST_AVAILABLE = True
except ImportError:
    _AST_AVAILABLE = False


def test_find_usages(project_root):
    from ckeditor_audit.tools.find_usages import find_usages
    result = find_usages(symbol="Plugin", output="json")
    assert result.token_savings.files_scanned > 0
    # 'Plugin' is referenced in the box/toolbar plugins and app/js/widget.js
    assert result.matches is not None and len(result.matches) > 0


def test_find_method_php(project_root):
    from ckeditor_audit.tools.find_method import find_method
    result = find_method(method_name="list")
    assert any(r.path.endswith("ArticleController.php") for r in result.results)


def test_find_extends_php(project_root):
    from ckeditor_audit.tools.find_extends import find_extends
    result = find_extends(class_name="AbstractController")
    assert any(r.class_name == "ArticleController" for r in result.results)


def test_find_implementations_php(project_root):
    from ckeditor_audit.tools.find_implementations import find_implementations
    result = find_implementations(interface_name="ControllerInterface")
    assert any(r.class_name == "ArticleController" for r in result.results)


def test_find_route_php_attribute(project_root):
    from ckeditor_audit.tools.find_route import find_route
    result = find_route(pattern="/articles")
    assert any(r.route == "/articles" for r in result.results)


def test_find_definition(project_root):
    from ckeditor_audit.tools.find_definition import find_definition
    result = find_definition(name="ArticleController")
    assert len(result.matches) > 0


def test_who_calls(project_root):
    from ckeditor_audit.tools.who_calls import who_calls
    # `this.doThing()` is called inside init() in app/js/widget.js
    result = who_calls(method="doThing")
    assert len(result.call_sites) >= 1


def test_what_calls_returns_model(project_root):
    """what_calls depends on enclosing-body detection; assert it runs and
    returns the expected structure without raising."""
    from ckeditor_audit.tools.what_calls import what_calls
    result = what_calls(method="init")
    assert hasattr(result, "outgoing_calls")
    assert isinstance(result.outgoing_calls, list)


def test_multi_search(project_root):
    from ckeditor_audit.tools.multi_search import multi_search, SearchQuery
    result = multi_search(queries=[
        SearchQuery(query="Plugin"),
        SearchQuery(query="Command"),
    ])
    assert len(result.results) == 2


@pytest.mark.skipif(
    not _AST_AVAILABLE,
    reason="ast-grep-py not installed",
)
def test_ast_search(project_root):
    from ckeditor_audit.tools.ast_search import ast_search
    result = ast_search(pattern="class $NAME extends $BASE", lang="javascript")
    assert hasattr(result, "matches")
    assert isinstance(result.matches, list)
