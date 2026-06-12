"""AST-grep Python bindings backend for structural code analysis.

Handles find_class, find_method, find_implementations, find_extends,
get_file_outline, and the generic ast_search tool.

Falls back gracefully if ast_grep_py is not installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator


def _is_available() -> bool:
    try:
        from ast_grep_py import SgRoot  # noqa: F401
        return True
    except ImportError:
        return False


def _walk_pruning_ext(
    directory: Path,
    extensions: tuple[str, ...],
    exclude_dirs: frozenset[str],
) -> Generator[Path, None, None]:
    """Walk directory pruning excluded dirs at the directory level."""
    import os as _os
    try:
        with _os.scandir(directory) as it:
            for entry in it:
                ep = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in exclude_dirs:
                        yield from _walk_pruning_ext(ep, extensions, exclude_dirs)
                elif entry.is_file():
                    if ep.suffix.lstrip(".") in extensions:
                        yield ep
    except (PermissionError, OSError):
        pass


def _iter_php_files(root: Path, exclude_dirs: frozenset[str]) -> Generator[Path, None, None]:
    yield from _walk_pruning_ext(root, ("php",), exclude_dirs)


def _iter_files_by_ext(
    root: Path, extensions: tuple[str, ...], exclude_dirs: frozenset[str]
) -> Generator[Path, None, None]:
    yield from _walk_pruning_ext(root, extensions, exclude_dirs)


def _lang_for_ext(ext: str) -> str | None:
    return {
        "php": "php",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "tsx",
    }.get(ext)


# ---------------------------------------------------------------------------
# find_class
# ---------------------------------------------------------------------------


def find_class(
    class_name: str,
    kind: str | None,
    root: Path,
    exclude_dirs: frozenset[str],
    extensions: tuple[str, ...] = ("php",),
) -> tuple[list[dict], int]:
    from ast_grep_py import SgRoot

    results: list[dict] = []
    files_searched = 0

    for path in _iter_files_by_ext(root, extensions, exclude_dirs):
        ext = path.suffix.lstrip(".")
        lang = _lang_for_ext(ext)
        if not lang:
            continue
        files_searched += 1
        rel = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        sg = SgRoot(source, lang)
        node = sg.root()

        if ext == "php":
            # Find namespace
            namespace = ""
            ns_matches = node.find_all({"rule": {"pattern": "namespace $NS;"}})
            for nm in ns_matches:
                ns_node = nm.get_match("NS")
                if ns_node:
                    namespace = ns_node.text()
                    break

            # class/interface/trait/enum declarations
            for decl_kind in ("class_declaration", "interface_declaration", "trait_declaration", "enum_declaration"):
                if kind and kind not in decl_kind:
                    continue
                for decl in node.find_all({"rule": {"kind": decl_kind}}):
                    name_node = decl.field("name")
                    if name_node and name_node.text() == class_name:
                        php_kind = decl_kind.replace("_declaration", "")
                        results.append({
                            "path": rel,
                            "line": decl.range().start.line + 1,
                            "kind": php_kind,
                            "namespace": namespace,
                        })
        else:
            # JS/TS/TSX/JSX: class_declaration always; interface_declaration only for TS/TSX
            supports_interface = lang in ("typescript", "tsx")
            decl_kinds = ["class_declaration"]
            if supports_interface:
                decl_kinds.append("interface_declaration")
            for decl_kind in decl_kinds:
                if kind and kind not in decl_kind.replace("_declaration", ""):
                    continue
                for decl in node.find_all({"rule": {"kind": decl_kind}}):
                    name_node = decl.field("name")
                    if name_node and name_node.text() == class_name:
                        results.append({
                            "path": rel,
                            "line": decl.range().start.line + 1,
                            "kind": decl_kind.replace("_declaration", ""),
                            "namespace": "",
                        })

    return results, files_searched


# ---------------------------------------------------------------------------
# find_method
# ---------------------------------------------------------------------------


def find_method(
    method_name: str,
    class_name: str | None,
    root: Path,
    extensions: tuple[str, ...],
    exclude_dirs: frozenset[str],
) -> tuple[list[dict], int]:
    from ast_grep_py import SgRoot

    results: list[dict] = []
    files_searched = 0
    name_lower = method_name.lower()

    for path in _iter_files_by_ext(root, extensions, exclude_dirs):
        ext = path.suffix.lstrip(".")
        lang = _lang_for_ext(ext)
        if not lang:
            continue

        files_searched += 1
        rel = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        sg = SgRoot(source, lang)
        node = sg.root()

        if ext == "php":
            for cls_decl in node.find_all({"rule": {"kind": "class_declaration"}}):
                cn_node = cls_decl.field("name")
                cn = cn_node.text() if cn_node else None
                if class_name and (not cn or cn.lower() != class_name.lower()):
                    continue
                for m in cls_decl.find_all({"rule": {"kind": "method_declaration"}}):
                    fn = m.field("name")
                    if fn and fn.text().lower() == name_lower:
                        vis = _get_php_visibility(m)
                        results.append({
                            "path": rel,
                            "line": m.range().start.line + 1,
                            "kind": "method",
                            "class_name": cn,
                            "visibility": vis,
                        })
            # Standalone functions
            if not class_name:
                for fn_decl in node.find_all({"rule": {"kind": "function_definition"}}):
                    fn = fn_decl.field("name")
                    if fn and fn.text().lower() == name_lower:
                        # Only if not inside a class
                        if not any(a.kind() == "class_declaration" for a in fn_decl.ancestors()):
                            results.append({
                                "path": rel,
                                "line": fn_decl.range().start.line + 1,
                                "kind": "function",
                                "class_name": None,
                                "visibility": None,
                            })

        elif ext in ("js", "ts", "tsx", "jsx"):
            for fn_decl in node.find_all({"rule": {"kind": "function_declaration"}}):
                fn = fn_decl.field("name")
                if fn and fn.text().lower() == name_lower:
                    results.append({
                        "path": rel,
                        "line": fn_decl.range().start.line + 1,
                        "kind": "function",
                        "class_name": None,
                        "visibility": None,
                    })
            for method in node.find_all({"rule": {"kind": "method_definition"}}):
                fn = method.field("name")
                if fn and fn.text().lower() == name_lower:
                    cls_name = _get_js_class_name(method)
                    results.append({
                        "path": rel,
                        "line": method.range().start.line + 1,
                        "kind": "method",
                        "class_name": cls_name,
                        "visibility": None,
                    })

    return results, files_searched


def _get_php_visibility(method_node) -> str:
    for child in method_node.children():
        t = child.text()
        if t in ("public", "protected", "private"):
            return t
    return "public"


def _get_js_class_name(method_node) -> str | None:
    for anc in method_node.ancestors():
        if anc.kind() == "class_declaration":
            fn = anc.field("name")
            return fn.text() if fn else None
    return None


# ---------------------------------------------------------------------------
# find_implementations
# ---------------------------------------------------------------------------


def find_implementations(
    interface_name: str,
    root: Path,
    exclude_dirs: frozenset[str],
    extensions: tuple[str, ...] = ("php",),
) -> tuple[list[dict], int]:
    from ast_grep_py import SgRoot

    results: list[dict] = []
    files_searched = 0

    for path in _iter_files_by_ext(root, extensions, exclude_dirs):
        ext = path.suffix.lstrip(".")
        # JavaScript has no interfaces — skip js/jsx
        if ext in ("js", "jsx"):
            continue
        lang = _lang_for_ext(ext)
        if not lang:
            continue
        files_searched += 1
        rel = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        sg = SgRoot(source, lang)
        node = sg.root()

        if ext == "php":
            namespace = _get_php_namespace(node)
            for cls_decl in node.find_all({"rule": {"kind": "class_declaration"}}):
                ifaces = _get_php_interfaces(cls_decl)
                iface_short = [i.split("\\")[-1] for i in ifaces]
                if interface_name in iface_short:
                    cn_node = cls_decl.field("name")
                    cn = cn_node.text() if cn_node else ""
                    results.append({
                        "path": rel,
                        "line": cls_decl.range().start.line + 1,
                        "class_name": cn,
                        "namespace": namespace,
                    })
        else:
            # TypeScript: implements clause in class_heritage
            for cls_decl in node.find_all({"rule": {"kind": "class_declaration"}}):
                ifaces = _get_ts_interfaces(cls_decl)
                if interface_name in ifaces:
                    cn_node = cls_decl.field("name")
                    cn = cn_node.text() if cn_node else ""
                    results.append({
                        "path": rel,
                        "line": cls_decl.range().start.line + 1,
                        "class_name": cn,
                        "namespace": "",
                    })

    return results, files_searched


# ---------------------------------------------------------------------------
# find_extends
# ---------------------------------------------------------------------------


def find_extends(
    base_class: str,
    root: Path,
    exclude_dirs: frozenset[str],
    extensions: tuple[str, ...] = ("php",),
) -> tuple[list[dict], int]:
    from ast_grep_py import SgRoot

    results: list[dict] = []
    files_searched = 0

    for path in _iter_files_by_ext(root, extensions, exclude_dirs):
        ext = path.suffix.lstrip(".")
        lang = _lang_for_ext(ext)
        if not lang:
            continue
        files_searched += 1
        rel = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        sg = SgRoot(source, lang)
        node = sg.root()

        if ext == "php":
            namespace = _get_php_namespace(node)
            for cls_decl in node.find_all({"rule": {"kind": "class_declaration"}}):
                parent = _get_php_parent(cls_decl)
                if parent and parent.split("\\")[-1] == base_class:
                    cn_node = cls_decl.field("name")
                    cn = cn_node.text() if cn_node else ""
                    results.append({
                        "path": rel,
                        "line": cls_decl.range().start.line + 1,
                        "class_name": cn,
                        "namespace": namespace,
                    })
        else:
            # JS/TS/TSX/JSX: class_heritage with extends clause
            for cls_decl in node.find_all({"rule": {"kind": "class_declaration"}}):
                parent = _get_js_parent(cls_decl)
                if parent and parent == base_class:
                    cn_node = cls_decl.field("name")
                    cn = cn_node.text() if cn_node else ""
                    results.append({
                        "path": rel,
                        "line": cls_decl.range().start.line + 1,
                        "class_name": cn,
                        "namespace": "",
                    })

    return results, files_searched


# ---------------------------------------------------------------------------
# get_file_outline
# ---------------------------------------------------------------------------


def get_file_outline(path_str: str, root: Path) -> list[dict]:
    from ast_grep_py import SgRoot

    full_path = root / path_str
    ext = full_path.suffix.lstrip(".")
    lang = _lang_for_ext(ext)
    if not lang:
        return []

    try:
        source = full_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    sg = SgRoot(source, lang)
    node = sg.root()
    results: list[dict] = []

    if ext == "php":
        for decl_kind in ("class_declaration", "interface_declaration", "trait_declaration", "enum_declaration"):
            for decl in node.find_all({"rule": {"kind": decl_kind}}):
                fn = decl.field("name")
                if fn:
                    results.append({
                        "kind": decl_kind.replace("_declaration", ""),
                        "name": fn.text(),
                        "line": decl.range().start.line + 1,
                    })
                for m in decl.find_all({"rule": {"kind": "method_declaration"}}):
                    mfn = m.field("name")
                    if mfn:
                        results.append({
                            "kind": "method",
                            "name": mfn.text(),
                            "line": m.range().start.line + 1,
                            "visibility": _get_php_visibility(m),
                        })
        # standalone functions
        for fn_decl in node.find_all({"rule": {"kind": "function_definition"}}):
            if not any(a.kind() == "class_declaration" for a in fn_decl.ancestors()):
                fn = fn_decl.field("name")
                if fn:
                    results.append({
                        "kind": "function",
                        "name": fn.text(),
                        "line": fn_decl.range().start.line + 1,
                    })

    elif ext in ("js", "ts", "tsx", "jsx"):
        for cls in node.find_all({"rule": {"kind": "class_declaration"}}):
            fn = cls.field("name")
            if fn:
                results.append({"kind": "class", "name": fn.text(), "line": cls.range().start.line + 1})
            for m in cls.find_all({"rule": {"kind": "method_definition"}}):
                mfn = m.field("name")
                if mfn:
                    results.append({
                        "kind": "method",
                        "name": mfn.text(),
                        "line": m.range().start.line + 1,
                        "visibility": "public",
                    })
        for fn_decl in node.find_all({"rule": {"kind": "function_declaration"}}):
            fn = fn_decl.field("name")
            if fn:
                results.append({"kind": "function", "name": fn.text(), "line": fn_decl.range().start.line + 1})
        # arrow functions assigned to const/let
        for lex in node.find_all({"rule": {"kind": "lexical_declaration"}}):
            for decl in lex.find_all({"rule": {"kind": "variable_declarator"}}):
                val = decl.field("value")
                if val and val.kind() in ("arrow_function", "function"):
                    fn = decl.field("name")
                    if fn:
                        results.append({"kind": "function", "name": fn.text(), "line": lex.range().start.line + 1})

    results.sort(key=lambda x: x["line"])
    return results


# ---------------------------------------------------------------------------
# ast_search — generic structural pattern search
# ---------------------------------------------------------------------------


def ast_search(
    pattern: str,
    lang: str,
    root: Path,
    path_glob: str | None,
    directory: str | None,
    extensions: tuple[str, ...],
    exclude_dirs: frozenset[str],
    max_results: int,
) -> tuple[list[dict], int]:
    """Search files for an ast-grep structural pattern."""
    from ast_grep_py import SgRoot
    import fnmatch

    results: list[dict] = []
    files_searched = 0
    search_root = root / directory if directory else root

    # Determine file extension for this lang
    lang_exts = {
        "php": ["php"],
        "javascript": ["js", "jsx"],
        "typescript": ["ts", "tsx"],
        "tsx": ["tsx"],
        "python": ["py"],
    }
    target_exts = lang_exts.get(lang.lower(), [lang.lower()])

    for path in search_root.rglob("*"):
        if not path.is_file():
            continue
        ext = path.suffix.lstrip(".")
        if ext not in target_exts:
            continue
        rel = path.relative_to(root)
        if any(part in exclude_dirs for part in rel.parts):
            continue
        if path_glob and not fnmatch.fnmatch(str(rel), path_glob):
            continue

        files_searched += 1
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        sg = SgRoot(source, lang)
        node = sg.root()
        for m in node.find_all({"rule": {"pattern": pattern}}):
            results.append({
                "path": str(rel),
                "line": m.range().start.line + 1,
                "snippet": m.text()[:200].replace("\n", " "),
            })
            if len(results) >= max_results:
                return results, files_searched

    return results, files_searched


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _get_php_namespace(node) -> str:
    ns_matches = node.find_all({"rule": {"pattern": "namespace $NS;"}})
    for nm in ns_matches:
        ns_node = nm.get_match("NS")
        if ns_node:
            return ns_node.text()
    return ""


def _get_php_interfaces(cls_decl) -> list[str]:
    """Return list of interface names from class_interface_clause."""
    for child in cls_decl.children():
        if child.kind() == "class_interface_clause":
            return [
                c.text()
                for c in child.children()
                if c.kind() not in ("implements", ",") and c.text().strip()
            ]
    return []


def _get_php_parent(cls_decl) -> str | None:
    """Return parent class name from base_clause (extends)."""
    for child in cls_decl.children():
        if child.kind() == "base_clause":
            for c in child.children():
                if c.kind() not in ("extends", ",") and c.text().strip():
                    return c.text()
    return None


def _get_js_parent(cls_decl) -> str | None:
    """Return parent class name from class_heritage (JS/TS extends).

    TypeScript wraps the extends part in an extends_clause node.
    JavaScript exposes extends + identifier directly in class_heritage.
    """
    for child in cls_decl.children():
        if child.kind() == "class_heritage":
            # TypeScript: extends_clause { extends, identifier }
            for c in child.children():
                if c.kind() == "extends_clause":
                    for cc in c.children():
                        if cc.kind() != "extends" and cc.text().strip():
                            return cc.text().split("<")[0].strip()
            # JavaScript: flat [extends(keyword), identifier, ...]
            found = False
            for c in child.children():
                if c.text() == "extends":
                    found = True
                elif found:
                    name = c.text().split("<")[0].strip()
                    if name and name != "implements":
                        return name
    return None


def _get_ts_interfaces(cls_decl) -> list[str]:
    """Return list of interface names from class_heritage implements clause.

    TypeScript wraps the implements part in an implements_clause node.
    Falls back to a flat keyword scan for edge cases.
    """
    for child in cls_decl.children():
        if child.kind() == "class_heritage":
            ifaces: list[str] = []
            # TypeScript: implements_clause { implements, type_identifier, ... }
            for c in child.children():
                if c.kind() == "implements_clause":
                    for cc in c.children():
                        if cc.kind() not in ("implements", ",") and cc.text().strip():
                            name = cc.text().split("<")[0].strip()
                            if name:
                                ifaces.append(name)
            if ifaces:
                return ifaces
            # Fallback: flat keyword scan
            found_implements = False
            for c in child.children():
                if c.text() == "implements":
                    found_implements = True
                elif c.text() == "extends":
                    found_implements = False
                elif found_implements and c.text() != ",":
                    name = c.text().split("<")[0].strip()
                    if name:
                        ifaces.append(name)
            return ifaces
    return []
