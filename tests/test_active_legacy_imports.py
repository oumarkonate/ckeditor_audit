"""
Tests pour find_active_legacy_entrypoint_imports() et les intégrations
audit_all / export_audit_report / audit_entrypoint.

Conventions :
- imports dans les tests (pas au top-level) pour que configure_env autouse s'exécute d'abord
- apply_overrides vient de conftest.py
"""

import json
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_ep(tmp_path, content: str):
    ep = tmp_path / "ckeditor.js"
    ep.write_text(content, encoding="utf-8")
    return ep


# ---------------------------------------------------------------------------
# Détection — cas nominaux
# ---------------------------------------------------------------------------

def test_symbol_commented_in_builtins_detected(apply_overrides, tmp_path):
    """Cas principal : import actif legacy, symbole commenté dans builtinPlugins → détecté."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [\n"
        "    Bold,\n"
        "    // Autosave,\n"
        "];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    issue = result[0]
    assert issue.symbol == "Autosave"
    assert issue.legacy_source == "@ckeditor/ckeditor5-autosave/src/autosave"
    assert issue.builtin_status == "commented"
    assert "from 'ckeditor5'" in issue.modern_replacement
    assert issue.line == 1


def test_symbol_missing_from_builtins(apply_overrides, tmp_path):
    """Import actif legacy, symbole absent de builtinPlugins → builtin_status=missing."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ Bold ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].builtin_status == "missing"


def test_multiple_imports_all_detected(apply_overrides, tmp_path):
    """Plusieurs imports actifs legacy → tous remontés."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "import Autoformat from '@ckeditor/ckeditor5-autoformat/src/autoformat';\n"
        "static builtinPlugins = [\n"
        "    // Autosave,\n"
        "    // Autoformat,\n"
        "];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    symbols = {r.symbol for r in result}
    assert symbols == {"Autosave", "Autoformat"}
    assert all(r.builtin_status == "commented" for r in result)


def test_legacy_source_exact(apply_overrides, tmp_path):
    """legacy_source préserve le chemin exact."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert result[0].legacy_source == "@ckeditor/ckeditor5-autosave/src/autosave"


def test_line_number_correct_when_not_first_line(apply_overrides, tmp_path):
    """line pointe vers la bonne ligne quand l'import n'est pas en 1ʳᵉ position."""
    ep = _write_ep(tmp_path, (
        "// some comment\n"
        "import Bold from 'ckeditor5';\n"
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].line == 3


def test_results_sorted_by_line(apply_overrides, tmp_path):
    """Résultat trié par numéro de ligne (ordre croissant)."""
    ep = _write_ep(tmp_path, (
        "import Autoformat from '@ckeditor/ckeditor5-autoformat/src/autoformat';\n"
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n // Autoformat,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    lines = [r.line for r in result]
    assert lines == sorted(lines)


# ---------------------------------------------------------------------------
# Variantes de parsing builtinPlugins
# ---------------------------------------------------------------------------

def test_multiline_builtins_commented(apply_overrides, tmp_path):
    """Bloc builtinPlugins multi-lignes, symbole commenté sur sa propre ligne."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [\n"
        "    Bold,\n"
        "    // Autosave,\n"
        "    Italic,\n"
        "];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].builtin_status == "commented"


def test_inline_comment_in_builtins_array(apply_overrides, tmp_path):
    """Commentaire de fin de ligne `[ // Autosave, ]` — ne doit PAS classer Autosave actif."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n"
        "];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].builtin_status == "commented"


def test_symbol_active_in_builtins_not_flagged(apply_overrides, tmp_path):
    """Symbole actif dans builtinPlugins → non remonté (autre problème, hors scope)."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ Autosave, Bold ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert result == []


def test_empty_builtins_array(apply_overrides, tmp_path):
    """Tableau builtinPlugins vide → import devient missing."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].builtin_status == "missing"


def test_builtins_without_static_prefix(apply_overrides, tmp_path):
    """Bloc `builtinPlugins = [...]` sans `static` → détecté pareil."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "builtinPlugins = [\n"
        "    // Autosave,\n"
        "];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].builtin_status == "commented"


def test_symbol_active_wins_over_commented_in_builtins(apply_overrides, tmp_path):
    """Symbole présent à la fois actif et commenté dans builtins → actif prime (non remonté)."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [\n"
        "    Autosave,\n"
        "    // Autosave,\n"
        "];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert result == []


# ---------------------------------------------------------------------------
# Exclusions — ne doivent PAS être remontées
# ---------------------------------------------------------------------------

def test_commented_import_not_detected(apply_overrides, tmp_path):
    """Import commenté (même legacy) → ignoré."""
    ep = _write_ep(tmp_path, (
        "// import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    assert find_active_legacy_entrypoint_imports() == []


def test_modern_import_not_detected(apply_overrides, tmp_path):
    """Import moderne depuis 'ckeditor5' → ignoré (pas un problème legacy)."""
    ep = _write_ep(tmp_path, (
        "import { Autosave } from 'ckeditor5';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    assert find_active_legacy_entrypoint_imports() == []


def test_custom_plugin_import_not_detected(apply_overrides, tmp_path):
    """Import depuis ./ckeditor5-* (plugin custom) → ignoré (couvert par le scan plugins)."""
    ep = _write_ep(tmp_path, (
        "import Modal from './ckeditor5-modal/src/modal';\n"
        "static builtinPlugins = [ // Modal,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    assert find_active_legacy_entrypoint_imports() == []


def test_non_ckeditor_import_not_detected(apply_overrides, tmp_path):
    """Import d'une lib tierce → ignoré."""
    ep = _write_ep(tmp_path, (
        "import lodash from 'lodash';\n"
        "static builtinPlugins = [];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    assert find_active_legacy_entrypoint_imports() == []


# ---------------------------------------------------------------------------
# Robustesse / cas limites
# ---------------------------------------------------------------------------

def test_no_entrypoint_configured_returns_empty(apply_overrides):
    """Pas d'entrypoint configuré → liste vide (pas de crash)."""
    apply_overrides(entrypoint=None)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    assert find_active_legacy_entrypoint_imports() == []


def test_entrypoint_file_missing_returns_empty(apply_overrides, tmp_path):
    """Fichier entrypoint configuré mais absent → liste vide."""
    apply_overrides(entrypoint=tmp_path / "nonexistent_ckeditor.js")
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    assert find_active_legacy_entrypoint_imports() == []


def test_empty_entrypoint_returns_empty(apply_overrides, tmp_path):
    """Fichier entrypoint vide → liste vide."""
    ep = _write_ep(tmp_path, "")
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    assert find_active_legacy_entrypoint_imports() == []


def test_no_builtinplugins_block_gives_missing(apply_overrides, tmp_path):
    """Fichier sans bloc builtinPlugins → imports → missing (pas de crash)."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "// no builtinPlugins here\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].builtin_status == "missing"


def test_modern_replacement_format(apply_overrides, tmp_path):
    """modern_replacement est au format `import { Symbol } from 'ckeditor5'`."""
    ep = _write_ep(tmp_path, (
        "import EasyImage from '@ckeditor/ckeditor5-easy-image/src/easyimage';\n"
        "static builtinPlugins = [];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert result[0].modern_replacement == "import { EasyImage } from 'ckeditor5'"


def test_leading_whitespace_in_import_tolerated(apply_overrides, tmp_path):
    """Import avec indentation → toujours capturé (regex tolère les espaces en tête)."""
    ep = _write_ep(tmp_path, (
        "    import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert len(result) == 1
    assert result[0].symbol == "Autosave"


def test_returns_pydantic_instances(apply_overrides, tmp_path):
    """Le retour est une liste d'instances BaseModel avec attributs accessibles."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import EntrypointImportIssue, find_active_legacy_entrypoint_imports
    result = find_active_legacy_entrypoint_imports()
    assert all(isinstance(i, EntrypointImportIssue) for i in result)
    issue = result[0]
    # Serialisation pydantic fonctionne
    d = issue.model_dump()
    assert set(d.keys()) == {"symbol", "legacy_source", "modern_replacement", "builtin_status", "line"}


# ---------------------------------------------------------------------------
# Intégration — audit_all
# ---------------------------------------------------------------------------

def test_audit_all_to_activate_count(apply_overrides, tmp_path):
    """audit_all retourne to_activate_imports == N."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.audit_all import audit_all
    report = audit_all()
    assert report.to_activate_imports == 1


def test_audit_all_entrypoint_issues_populated(apply_overrides, tmp_path):
    """audit_all.entrypoint_issues contient les EntrypointImportIssue attendus."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.audit_all import audit_all
    from ckeditor_audit.lib.scanner import EntrypointImportIssue
    report = audit_all()
    assert len(report.entrypoint_issues) == 1
    assert isinstance(report.entrypoint_issues[0], EntrypointImportIssue)
    assert report.entrypoint_issues[0].symbol == "Autosave"


def test_audit_all_defaults_when_no_entrypoint(apply_overrides):
    """Sans entrypoint : to_activate_imports == 0, entrypoint_issues == []."""
    apply_overrides(entrypoint=None)
    from ckeditor_audit.tools.audit_all import audit_all
    report = audit_all()
    assert report.to_activate_imports == 0
    assert report.entrypoint_issues == []


def test_audit_all_existing_counters_unaffected(apply_overrides, tmp_path):
    """Les compteurs existants (total, migrated, etc.) restent cohérents."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.audit_all import audit_all
    report = audit_all()
    # 4 plugins (box=migrated, toolbar=partial, image=not_migrated, empty=no_imports)
    assert report.total == 4
    assert report.migrated == 1
    assert report.partial == 1
    assert report.not_migrated == 1
    assert report.no_imports == 1


def test_audit_all_model_dump_no_error(apply_overrides, tmp_path):
    """report.model_dump() + json.dumps ne lèvent pas d'erreur."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.audit_all import audit_all
    report = audit_all()
    dumped = report.model_dump()
    json.dumps(dumped)  # ne doit pas lever


# ---------------------------------------------------------------------------
# Intégration — export_audit_report Markdown
# ---------------------------------------------------------------------------

def test_export_markdown_contains_to_activate_section(apply_overrides, tmp_path):
    """Rapport Markdown contient section 🔌 À activer avec les bonnes valeurs."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    result = export_audit_report(format="markdown")
    content = result.content
    assert "🔌" in content
    assert "Autosave" in content
    assert "@ckeditor/ckeditor5-autosave/src/autosave" in content
    assert "from 'ckeditor5'" in content


def test_export_markdown_no_section_when_no_issues(apply_overrides, tmp_path):
    """Pas de section 🔌 si aucun cas détecté."""
    ep = _write_ep(tmp_path, (
        "import { Bold } from 'ckeditor5';\n"
        "static builtinPlugins = [ Bold ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    result = export_audit_report(format="markdown")
    # "À activer (" n'existe que dans l'en-tête de section ## 🔌 À activer (N imports)
    # (le tableau Avancement a "| 🔌 À activer |" avec des pipes, jamais des parenthèses)
    assert "À activer (" not in result.content


def test_export_markdown_section_order(apply_overrides, tmp_path):
    """La section 🔌 À activer apparaît après 🗑️ À supprimer et avant ❌ Non migrés."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(
        overrides={"plugins": {"ckeditor5-empty": {"status": "to_delete", "reason": "Test"}}},
        entrypoint=ep,
    )
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    content = export_audit_report(format="markdown").content
    # On cherche les formes avec parenthèses "À supprimer (", "À activer (" et "Non migrés ("
    # qui n'existent QUE dans les en-têtes de section (jamais dans le tableau Avancement).
    idx_delete = content.index("À supprimer (")
    idx_activate = content.index("À activer (")
    idx_nm = content.index("Non migrés (")
    assert idx_delete < idx_activate < idx_nm


def test_export_markdown_pipe_escaped_in_table(apply_overrides, tmp_path):
    """Les `|` dans les chemins sont échappés pour ne pas casser le tableau Markdown."""
    # Le chemin @ckeditor/... ne contient pas de pipe, mais on vérifie que la table est valide
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    content = export_audit_report(format="markdown").content
    # Vérifier que la ligne de table contient 4 séparateurs de colonnes (5 cellules)
    table_lines = [l for l in content.splitlines() if "Autosave" in l and l.startswith("|")]
    assert len(table_lines) == 1
    assert table_lines[0].count("|") >= 4


def test_export_markdown_existing_sections_present(apply_overrides, tmp_path):
    """Les sections existantes restent présentes quand il y a aussi des 'à activer'."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    content = export_audit_report(format="markdown").content
    assert "❌ Non migrés" in content
    assert "⚠️ Partiels" in content
    assert "✅ Migrés" in content


def test_export_advance_table_has_to_activate_line(apply_overrides, tmp_path):
    """Le tableau Avancement contient la ligne 🔌 À activer."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    content = export_audit_report(format="markdown").content
    lines_with_activate = [l for l in content.splitlines() if "À activer" in l and "|" in l]
    # Au moins une ligne dans le tableau d'avancement
    assert len(lines_with_activate) >= 1


# ---------------------------------------------------------------------------
# Intégration — export_audit_report JSON
# ---------------------------------------------------------------------------

def test_export_json_has_to_activate_group(apply_overrides, tmp_path):
    """JSON contient groups.to_activate avec les champs attendus."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    data = json.loads(export_audit_report(format="json").content)
    assert "to_activate" in data["groups"]
    assert len(data["groups"]["to_activate"]) == 1
    entry = data["groups"]["to_activate"][0]
    assert set(entry.keys()) >= {"symbol", "legacy_source", "modern_replacement", "builtin_status", "line"}
    assert entry["symbol"] == "Autosave"


def test_export_json_to_activate_empty_when_no_issues(apply_overrides, tmp_path):
    """groups.to_activate est vide quand aucun cas."""
    ep = _write_ep(tmp_path, (
        "import { Bold } from 'ckeditor5';\n"
        "static builtinPlugins = [ Bold ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.export_audit_report import export_audit_report
    data = json.loads(export_audit_report(format="json").content)
    assert data["groups"]["to_activate"] == []


# ---------------------------------------------------------------------------
# Intégration — audit_entrypoint (outil MCP)
# ---------------------------------------------------------------------------

def test_audit_entrypoint_tool_returns_issues(apply_overrides, tmp_path):
    """audit_entrypoint() retourne les mêmes issues que le scanner."""
    ep = _write_ep(tmp_path, (
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.tools.audit_entrypoint import audit_entrypoint
    from ckeditor_audit.lib.scanner import EntrypointImportIssue
    result = audit_entrypoint()
    assert len(result) == 1
    assert isinstance(result[0], EntrypointImportIssue)
    assert result[0].symbol == "Autosave"


def test_audit_entrypoint_tool_returns_empty_without_config(apply_overrides):
    """audit_entrypoint() → [] quand pas d'entrypoint."""
    apply_overrides(entrypoint=None)
    from ckeditor_audit.tools.audit_entrypoint import audit_entrypoint
    assert audit_entrypoint() == []


def test_server_imports_audit_entrypoint():
    """server.py importe et enregistre audit_entrypoint sans erreur."""
    import ckeditor_audit.server  # ne doit pas lever


# ---------------------------------------------------------------------------
# Non-régression — fonctions existantes inchangées
# ---------------------------------------------------------------------------

def test_parse_entrypoint_unaffected(apply_overrides, tmp_path):
    """parse_entrypoint() existant retourne toujours active/commented par nom de plugin."""
    ep = _write_ep(tmp_path, (
        "import Box from './ckeditor5-box/src/box';\n"
        "// import Image from './ckeditor5-image/src/image';\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import parse_entrypoint
    cross = parse_entrypoint()
    assert "ckeditor5-box" in cross["active"]
    assert "ckeditor5-image" in cross["commented"]


def test_detect_status_unaffected(apply_overrides, project_root):
    """detect_status() pour les plugins custom reste inchangé."""
    apply_overrides()
    from ckeditor_audit.lib.scanner import detect_status
    assert detect_status("ckeditor5-box") == "migrated"
    assert detect_status("ckeditor5-image") == "not_migrated"
    assert detect_status("ckeditor5-toolbar") == "partial"


def test_find_active_legacy_does_not_affect_parse_entrypoint(apply_overrides, tmp_path):
    """Appeler find_active_legacy_entrypoint_imports n'altère pas parse_entrypoint."""
    ep = _write_ep(tmp_path, (
        "import Box from './ckeditor5-box/src/box';\n"
        "import Autosave from '@ckeditor/ckeditor5-autosave/src/autosave';\n"
        "static builtinPlugins = [ // Autosave,\n ];\n"
    ))
    apply_overrides(entrypoint=ep)
    from ckeditor_audit.lib.scanner import find_active_legacy_entrypoint_imports, parse_entrypoint
    find_active_legacy_entrypoint_imports()
    cross = parse_entrypoint()
    assert "ckeditor5-box" in cross["active"]
