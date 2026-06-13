"""Tests for MCP resource and prompt registration.

A minimal stub MCP server captures the registered callables so we can invoke
them directly and assert on their output, without spinning up a real server.
"""

import json


class _StubMCP:
    def __init__(self):
        self.resources = {}
        self.prompts = {}

    def resource(self, uri):
        def deco(fn):
            self.resources[uri] = fn
            return fn
        return deco

    def prompt(self):
        def deco(fn):
            self.prompts[fn.__name__] = fn
            return fn
        return deco


def test_patterns_resource(project_root):
    from ckeditor_audit.resources import register_resources
    stub = _StubMCP()
    register_resources(stub)
    assert "ckeditor://patterns" in stub.resources
    payload = stub.resources["ckeditor://patterns"]()
    data = json.loads(payload)
    assert isinstance(data, list) and len(data) > 0
    assert "legacy" in data[0] and "replacement" in data[0]


def test_migrate_plugin_prompt(project_root):
    from ckeditor_audit.prompts import register_prompts
    stub = _StubMCP()
    register_prompts(stub)
    assert "migrate_plugin" in stub.prompts
    messages = stub.prompts["migrate_plugin"]("ckeditor5-image")
    assert len(messages) == 1
    text = messages[0].content.text
    assert "Migrate CKEditor plugin" in text
    # not_migrated plugin → at least one detected legacy pattern is listed
    assert "Detected legacy patterns" in text


def test_migrate_plugin_prompt_no_imports(project_root):
    from ckeditor_audit.prompts import register_prompts
    stub = _StubMCP()
    register_prompts(stub)
    messages = stub.prompts["migrate_plugin"]("ckeditor5-empty")
    text = messages[0].content.text
    assert "No CKEditor imports" in text
