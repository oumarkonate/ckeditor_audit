"""
MCP server entry point.

MCPServer is the high-level class from the official MCP Python SDK.
Each tool is registered via the mcp.tool() decorator defined in its own module.
MCPServer reads the function's type hints to auto-generate the JSON input/output
schemas that Claude uses to call the tool correctly.
"""

import logging
import sys

from mcp.server.mcpserver import MCPServer

# --- CKEditor audit tools ---
from ckeditor_audit.tools.list_patterns import list_patterns
from ckeditor_audit.tools.audit_plugin import audit_plugin
from ckeditor_audit.tools.audit_all import audit_all
from ckeditor_audit.tools.audit_entrypoint import audit_entrypoint
from ckeditor_audit.tools.find_plugin_usages import find_plugin_usages
from ckeditor_audit.tools.audit_dependencies import audit_dependencies

# --- Migration assistance tools ---
from ckeditor_audit.tools.suggest_migration import suggest_migration
from ckeditor_audit.tools.validate_migration import validate_migration
from ckeditor_audit.tools.export_audit_report import export_audit_report

# --- Navigation & file I/O ---
from ckeditor_audit.tools.find_files import find_files
from ckeditor_audit.tools.directory_tree import directory_tree
from ckeditor_audit.tools.read_file import read_file
from ckeditor_audit.tools.get_file_outline import get_file_outline

# --- Search (ripgrep-backed with Python fallback) ---
from ckeditor_audit.tools.grep_code import grep_code
from ckeditor_audit.tools.grep_with_context import grep_with_context
from ckeditor_audit.tools.count_matches import count_matches
from ckeditor_audit.tools.multi_search import multi_search

# --- AST structural search ---
from ckeditor_audit.tools.ast_search import ast_search

# --- Code intelligence ---
from ckeditor_audit.tools.find_class import find_class
from ckeditor_audit.tools.find_method import find_method
from ckeditor_audit.tools.find_implementations import find_implementations
from ckeditor_audit.tools.find_extends import find_extends
from ckeditor_audit.tools.find_definition import find_definition
from ckeditor_audit.tools.find_usages import find_usages
from ckeditor_audit.tools.who_calls import who_calls
from ckeditor_audit.tools.what_calls import what_calls

# --- Framework-specific (useful for PHP config files and test discovery) ---
from ckeditor_audit.tools.find_route import find_route
from ckeditor_audit.tools.find_tests import find_tests
from ckeditor_audit.tools.find_source import find_source

# --- Git-aware search ---
from ckeditor_audit.tools.git_changed_files import git_changed_files
from ckeditor_audit.tools.grep_changed import grep_changed
from ckeditor_audit.tools.find_in_file_diff import find_in_file_diff

# --- MCP Resources and Prompts ---
from ckeditor_audit.resources import register_resources
from ckeditor_audit.prompts import register_prompts

# ---------------------------------------------------------------------------
# Logging — must go to stderr (stdout is reserved for JSON-RPC on stdio transport)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ckeditor-audit")

# ---------------------------------------------------------------------------
# Server declaration
# ---------------------------------------------------------------------------

mcp = MCPServer(
    name="ckeditor-audit",
    title="CKEditor Migration Audit",
    description=(
        "Read-only audit server for CKEditor custom plugins. "
        "Reports migration status, detects legacy patterns, and maps plugin/config dependencies. "
        "Full-featured code search powered by ripgrep (when available) and ast-grep for JS/TS. "
        "Includes migration assistance, report export, and guided prompts."
    ),
)

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

# --- CKEditor audit (domain-specific) ---
mcp.tool()(list_patterns)
mcp.tool()(audit_plugin)
mcp.tool()(audit_all)
mcp.tool()(audit_entrypoint)
mcp.tool()(find_plugin_usages)
mcp.tool()(audit_dependencies)

# --- Migration assistance ---
mcp.tool()(suggest_migration)
mcp.tool()(validate_migration)
mcp.tool()(export_audit_report)

# --- Navigation & file I/O ---
mcp.tool()(find_files)
mcp.tool()(directory_tree)
mcp.tool()(read_file)
mcp.tool()(get_file_outline)

# --- Search ---
mcp.tool()(grep_code)
mcp.tool()(grep_with_context)
mcp.tool()(count_matches)
mcp.tool()(multi_search)

# --- AST structural search ---
mcp.tool()(ast_search)

# --- Code intelligence ---
mcp.tool()(find_class)
mcp.tool()(find_method)
mcp.tool()(find_implementations)
mcp.tool()(find_extends)
mcp.tool()(find_definition)
mcp.tool()(find_usages)
mcp.tool()(who_calls)
mcp.tool()(what_calls)

# --- Framework-specific ---
mcp.tool()(find_route)
mcp.tool()(find_tests)
mcp.tool()(find_source)

# --- Git-aware search ---
mcp.tool()(git_changed_files)
mcp.tool()(grep_changed)
mcp.tool()(find_in_file_diff)

# ---------------------------------------------------------------------------
# Resources & Prompts
# ---------------------------------------------------------------------------

register_resources(mcp)
register_prompts(mcp)

logger.info("ckeditor-audit server ready — 34 tools, 1 resource, 1 prompt registered")
