"""
Centralized tuning constants.

Token-saving estimates and subprocess timeouts live here so the numbers stay
consistent across tools instead of being redefined per module. These are
heuristics used only for reporting and safety — never for correctness.
"""

# --- Token-saving estimates -------------------------------------------------
# Rough number of tokens Claude would otherwise spend reading one file directly.
TOKENS_PER_SOURCE_FILE = 500
TOKENS_PER_CONFIG_FILE = 300
TOKENS_PER_PLUGIN_FILE = 400    # generic per-file estimate (suggest/validate)
TOKENS_PER_PLUGIN_REPORT = 800  # full per-plugin report (export_audit_report)

# --- Subprocess timeouts (seconds) ------------------------------------------
GIT_TIMEOUT = 10        # short git metadata / status calls
SUBPROCESS_TIMEOUT = 30  # longer external calls (diffs, ripgrep)
