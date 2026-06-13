import re
from pathlib import Path
from typing import Generator

from ckeditor_audit.config import settings

# Git-aware helpers live in their own module now; re-exported here so existing
# `from ckeditor_audit.lib.searcher import git_changed_files` imports keep working.
from ckeditor_audit.lib.search.git_ops import (  # noqa: F401
    _assert_git_repo,
    find_in_file_diff,
    git_changed_files,
    grep_changed,
)


def _is_excluded(path: Path) -> bool:
    return any(part in settings.exclude_dirs for part in path.parts)


def _walk_pruning(
    directory: Path,
    extensions: tuple[str, ...],
    project_root: Path | None = None,
) -> Generator[Path, None, None]:
    """Walk directory tree pruning excluded dirs at the entry point (much faster than rglob)."""
    import os as _os
    root = project_root or settings.project_root
    try:
        with _os.scandir(directory) as it:
            for entry in it:
                ep = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in settings.exclude_dirs:
                        yield from _walk_pruning(ep, extensions, root)
                elif entry.is_file():
                    if ep.suffix.lstrip(".") in extensions:
                        yield ep
    except (PermissionError, OSError):
        pass


def iter_files(root: Path, extensions: tuple[str, ...] | None = None) -> Generator[Path, None, None]:
    exts = extensions or settings.extensions
    yield from _walk_pruning(root, exts, settings.project_root)


# ---------------------------------------------------------------------------
# Backend dispatcher helpers
# ---------------------------------------------------------------------------

def _use_rg() -> bool:
    return settings.backend == "rg" and settings.rg_available


def _use_ast_grep() -> bool:
    return settings.ast_grep_available


def find_files(
    pattern: str,
    directory: str | None = None,
    extension: str | None = None,
) -> tuple[list[dict], int]:
    root = settings.project_root / directory if directory else settings.project_root
    if not root.exists():
        return [], 0

    exts = (extension.lstrip("."),) if extension else settings.extensions
    results = []
    files_checked = 0

    for path in _walk_pruning(root, exts):
        rel = path.relative_to(settings.project_root)
        files_checked += 1
        if pattern.lower() in path.name.lower():
            results.append({"path": str(rel), "name": path.name})
        if len(results) >= settings.max_results:
            break

    return results, files_checked


def grep_code(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool | None = None,
    multiline: bool = False,
) -> tuple[list[dict], int]:
    limit = max_results or settings.max_results
    rg_ignore = respect_gitignore if respect_gitignore is not None else settings.respect_gitignore

    if _use_rg():
        from ckeditor_audit.lib.backends.ripgrep import grep_code as rg_grep
        return rg_grep(
            query=query,
            root=settings.project_root,
            directory=directory,
            extensions=extensions,
            settings_extensions=settings.extensions,
            settings_exclude_dirs=settings.exclude_dirs,
            max_results=limit,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            fixed_string=fixed_string,
            path_glob=path_glob,
            respect_gitignore=rg_ignore,
            multiline=multiline,
        )

    # Python fallback
    root = settings.project_root / directory if directory else settings.project_root
    if not root.exists():
        return [], 0

    exts = tuple(e.lstrip(".") for e in extensions) if extensions else settings.extensions
    results = []
    files_searched = 0

    if fixed_string:
        pattern = re.compile(re.escape(query), re.IGNORECASE if case_sensitive == "smart" else 0)
    else:
        try:
            flags = re.IGNORECASE if case_sensitive in (False, "smart") else 0
            pattern = re.compile(query, flags)
        except re.error:
            pattern = re.compile(re.escape(query))

    word_re = re.compile(r"\b" + re.escape(query) + r"\b") if whole_word and fixed_string else None

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(settings.project_root)
        if _is_excluded(rel):
            continue
        if path.suffix.lstrip(".") not in exts:
            continue

        files_searched += 1
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        if word_re and not word_re.search(line):
                            continue
                        snippet = line.strip()[:120]
                        results.append({"path": str(rel), "line": lineno, "snippet": snippet})
                        if len(results) >= limit:
                            return results, files_searched
        except OSError:
            continue

    return results, files_searched


_CLASS_PATTERN = re.compile(
    r"^(?:abstract\s+|final\s+|readonly\s+)?"
    r"(class|interface|trait|enum)\s+(\w+)"
)
_NAMESPACE_PATTERN = re.compile(r"^namespace\s+([\w\\]+)\s*;")


def find_class(
    class_name: str,
    kind: str | None = None,
    fuzzy: bool = False,
) -> tuple[list[dict], int]:
    if _use_ast_grep():
        from ckeditor_audit.lib.backends.astgrep import find_class as ag_find_class
        if fuzzy:
            from ckeditor_audit.lib.fuzzy import fuzzy_match_items
            results, files_searched = _find_class_regex_all(kind)
            results = fuzzy_match_items(class_name, results, "name_key")
            return results, files_searched
        return ag_find_class(class_name, kind, settings.project_root, settings.exclude_dirs, settings.extensions)

    # Python regex fallback
    root = settings.project_root
    results = []
    files_searched = 0

    _JS_EXTS = ("js", "ts", "tsx", "jsx")
    for path in _walk_pruning(root, ("php",) + _JS_EXTS):
        ext = path.suffix.lstrip(".")
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue

        files_searched += 1
        namespace = ""
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    stripped = line.strip()
                    if ext == "php":
                        ns_match = _NAMESPACE_PATTERN.match(stripped)
                        if ns_match:
                            namespace = ns_match.group(1)
                            continue
                        cls_match = _CLASS_PATTERN.match(stripped)
                        if cls_match:
                            found_kind, found_name = cls_match.group(1), cls_match.group(2)
                            if found_name == class_name:
                                if kind is None or found_kind == kind:
                                    results.append({
                                        "path": str(rel),
                                        "line": lineno,
                                        "kind": found_kind,
                                        "namespace": namespace,
                                    })
                    elif ext in _JS_EXTS:
                        m = _JS_CLASS_RE.match(stripped)
                        if m and m.group(1) == class_name:
                            if kind is None or kind == "class":
                                results.append({
                                    "path": str(rel),
                                    "line": lineno,
                                    "kind": "class",
                                    "namespace": "",
                                })
        except OSError:
            continue

    if fuzzy and not results:
        from ckeditor_audit.lib.fuzzy import fuzzy_match_items
        all_results, files_searched = _find_class_regex_all(kind)
        results = fuzzy_match_items(class_name, all_results, "name_key")

    return results, files_searched


def _find_class_regex_all(kind: str | None) -> tuple[list[dict], int]:
    """Collect all class declarations for fuzzy matching."""
    root = settings.project_root
    results = []
    files_searched = 0
    _JS_EXTS = ("js", "ts", "tsx", "jsx")
    for path in _walk_pruning(root, ("php",) + _JS_EXTS):
        ext = path.suffix.lstrip(".")
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue
        files_searched += 1
        namespace = ""
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    stripped = line.strip()
                    if ext == "php":
                        ns_match = _NAMESPACE_PATTERN.match(stripped)
                        if ns_match:
                            namespace = ns_match.group(1)
                            continue
                        cls_match = _CLASS_PATTERN.match(stripped)
                        if cls_match:
                            found_kind, found_name = cls_match.group(1), cls_match.group(2)
                            if kind is None or found_kind == kind:
                                results.append({
                                    "path": str(rel),
                                    "line": lineno,
                                    "kind": found_kind,
                                    "namespace": namespace,
                                    "name_key": found_name,
                                })
                    elif ext in _JS_EXTS:
                        m = _JS_CLASS_RE.match(stripped)
                        if m and (kind is None or kind == "class"):
                            results.append({
                                "path": str(rel),
                                "line": lineno,
                                "kind": "class",
                                "namespace": "",
                                "name_key": m.group(1),
                            })
        except OSError:
            continue
    return results, files_searched


# ---------------------------------------------------------------------------
# Tier 1 — read_file
# ---------------------------------------------------------------------------

_DEFAULT_LINE_CAP = 200


def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> tuple[str, int]:
    """Returns (content, total_lines)."""
    full_path = settings.project_root / path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not full_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    with open(full_path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    total = len(lines)
    start = (start_line - 1) if start_line else 0
    end = end_line if end_line else (start + _DEFAULT_LINE_CAP if not start_line else min(start + _DEFAULT_LINE_CAP, total))
    end = min(end, total)

    return "".join(lines[start:end]), total


# ---------------------------------------------------------------------------
# Tier 1 — get_file_outline
# ---------------------------------------------------------------------------

_PHP_CLASS_RE = re.compile(
    r"^(?:abstract\s+|final\s+|readonly\s+)?(class|interface|trait|enum)\s+(\w+)"
)
_PHP_METHOD_RE = re.compile(
    r"^\s*(?:(public|protected|private)\s+)?(?:static\s+)?(?:abstract\s+|final\s+)?function\s+(\w+)\s*\("
)
_JS_CLASS_RE = re.compile(r"^(?:export\s+)?(?:default\s+)?class\s+(\w+)")
_JS_FUNC_RE = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(")
_JS_ARROW_RE = re.compile(r"^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\(")
_TS_METHOD_RE = re.compile(
    r"^\s+(?:(public|protected|private|readonly)\s+)?(?:static\s+)?(?:async\s+)?(\w+)\s*\("
)


def get_file_outline(path: str) -> list[dict]:
    full_path = settings.project_root / path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = full_path.suffix.lstrip(".")
    results: list[dict] = []
    in_class = False

    with open(full_path, encoding="utf-8", errors="ignore") as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue

            if ext == "php":
                m = _PHP_CLASS_RE.match(stripped)
                if m:
                    results.append({"kind": m.group(1), "name": m.group(2), "line": lineno})
                    continue
                m = _PHP_METHOD_RE.match(stripped)
                if m:
                    results.append({
                        "kind": "method",
                        "name": m.group(2),
                        "line": lineno,
                        "visibility": m.group(1) or "public",
                    })

            elif ext in ("js", "ts", "tsx", "jsx"):
                m = _JS_CLASS_RE.match(stripped)
                if m:
                    results.append({"kind": "class", "name": m.group(1), "line": lineno})
                    in_class = True
                    continue
                m = _JS_FUNC_RE.match(stripped)
                if m:
                    results.append({"kind": "function", "name": m.group(1), "line": lineno})
                    continue
                m = _JS_ARROW_RE.match(stripped)
                if m:
                    results.append({"kind": "function", "name": m.group(1), "line": lineno})
                    continue
                if in_class and ext in ("ts", "tsx"):
                    m = _TS_METHOD_RE.match(line)
                    if m and m.group(2) not in ("if", "for", "while", "switch", "catch"):
                        results.append({
                            "kind": "method",
                            "name": m.group(2),
                            "line": lineno,
                            "visibility": m.group(1) or "public",
                        })

    return results


# ---------------------------------------------------------------------------
# Tier 1 — grep_with_context
# ---------------------------------------------------------------------------


def grep_with_context(
    query: str,
    context_lines: int = 3,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool | None = None,
    multiline: bool = False,
) -> tuple[list[dict], int]:
    limit = max_results or settings.max_results
    ctx = min(max(context_lines, 0), 10)
    rg_ignore = respect_gitignore if respect_gitignore is not None else settings.respect_gitignore

    if _use_rg():
        from ckeditor_audit.lib.backends.ripgrep import grep_with_context as rg_ctx
        return rg_ctx(
            query=query,
            context_lines=ctx,
            root=settings.project_root,
            directory=directory,
            extensions=extensions,
            settings_extensions=settings.extensions,
            settings_exclude_dirs=settings.exclude_dirs,
            max_results=limit,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            fixed_string=fixed_string,
            path_glob=path_glob,
            respect_gitignore=rg_ignore,
            multiline=multiline,
        )

    root = settings.project_root / directory if directory else settings.project_root
    if not root.exists():
        return [], 0

    exts = tuple(e.lstrip(".") for e in extensions) if extensions else settings.extensions
    results: list[dict] = []
    files_searched = 0

    try:
        pattern = re.compile(query)
    except re.error:
        pattern = re.compile(re.escape(query))

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(settings.project_root)
        if _is_excluded(rel):
            continue
        if path.suffix.lstrip(".") not in exts:
            continue

        files_searched += 1
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                file_lines = f.readlines()

            for lineno, line in enumerate(file_lines, 1):
                if not pattern.search(line):
                    continue

                before_start = max(0, lineno - 1 - ctx)
                after_end = min(len(file_lines), lineno + ctx)

                before = [file_lines[i].rstrip() for i in range(before_start, lineno - 1)]
                after = [file_lines[i].rstrip() for i in range(lineno, after_end)]

                results.append({
                    "path": str(rel),
                    "line": lineno,
                    "snippet": line.strip()[:120],
                    "before": before,
                    "after": after,
                })
                if len(results) >= limit:
                    return results, files_searched
        except OSError:
            continue

    return results, files_searched


# ---------------------------------------------------------------------------
# Tier 1 — directory_tree
# ---------------------------------------------------------------------------


def directory_tree(
    directory: str | None = None,
    depth: int = 3,
    extensions_filter: list[str] | None = None,
) -> tuple[str, int]:
    """Returns (tree_string, files_traversed)."""
    root = settings.project_root / directory if directory else settings.project_root
    if not root.exists():
        return f"Directory not found: {directory or '.'}", 0

    max_depth = min(max(depth, 1), 6)
    exts = tuple(e.lstrip(".") for e in extensions_filter) if extensions_filter else None
    lines: list[str] = []
    files_traversed = 0

    def _walk(current: Path, prefix: str, current_depth: int) -> None:
        nonlocal files_traversed
        if current_depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return

        visible = []
        for entry in entries:
            rel = entry.relative_to(settings.project_root)
            if _is_excluded(rel):
                continue
            if entry.is_file():
                files_traversed += 1
                if exts and entry.suffix.lstrip(".") not in exts:
                    continue
            visible.append(entry)

        for i, entry in enumerate(visible):
            is_last = i == len(visible) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                child_prefix = prefix + ("    " if is_last else "│   ")
                if current_depth < max_depth:
                    _walk(entry, child_prefix, current_depth + 1)
                else:
                    lines.append(f"{child_prefix}└── ...")

    root_label = str(root.relative_to(settings.project_root)) if directory else "."
    lines.append(root_label)
    _walk(root, "", 1)
    return "\n".join(lines), files_traversed


# ---------------------------------------------------------------------------
# Tier 1 — find_method
# ---------------------------------------------------------------------------

_PHP_CLASS_NAME_RE = re.compile(
    r"^(?:abstract\s+|final\s+|readonly\s+)?(?:class|interface|trait|enum)\s+(\w+)"
)
_PHP_FUNC_DECL_RE = re.compile(
    r"^\s*(?:(public|protected|private)\s+)?(?:static\s+)?(?:abstract\s+|final\s+)?function\s+(\w+)\s*\("
)
_JS_METHOD_DECL_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|static|async|readonly)\s+)*(\w+)\s*\("
)


def find_method(
    method_name: str,
    class_name: str | None = None,
    directory: str | None = None,
) -> tuple[list[dict], int]:
    root = settings.project_root / directory if directory else settings.project_root
    if not root.exists():
        return [], 0

    if _use_ast_grep():
        from ckeditor_audit.lib.backends.astgrep import find_method as ag_find_method
        return ag_find_method(method_name, class_name, root, settings.extensions, settings.exclude_dirs)

    name_lower = method_name.lower()
    results: list[dict] = []
    files_searched = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(settings.project_root)
        if _is_excluded(rel):
            continue
        ext = path.suffix.lstrip(".")
        if ext not in settings.extensions:
            continue

        files_searched += 1
        current_class: str | None = None

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    stripped = line.strip()

                    if ext == "php":
                        cm = _PHP_CLASS_NAME_RE.match(stripped)
                        if cm:
                            current_class = cm.group(1)
                            continue

                        m = _PHP_FUNC_DECL_RE.match(stripped)
                        if m:
                            vis, fname = m.group(1), m.group(2)
                            if fname.lower() == name_lower:
                                if class_name is None or (
                                    current_class and current_class.lower() == class_name.lower()
                                ):
                                    results.append({
                                        "path": str(rel),
                                        "line": lineno,
                                        "kind": "method" if current_class else "function",
                                        "class_name": current_class,
                                        "visibility": vis or "public",
                                    })

                    elif ext in ("js", "ts", "tsx", "jsx"):
                        m = _JS_FUNC_RE.match(stripped)
                        if m and m.group(1).lower() == name_lower:
                            results.append({
                                "path": str(rel),
                                "line": lineno,
                                "kind": "function",
                                "class_name": None,
                                "visibility": None,
                            })
                            continue
                        m = _JS_ARROW_RE.match(stripped)
                        if m and m.group(1).lower() == name_lower:
                            results.append({
                                "path": str(rel),
                                "line": lineno,
                                "kind": "function",
                                "class_name": None,
                                "visibility": None,
                            })
        except OSError:
            continue

    return results, files_searched


# ---------------------------------------------------------------------------
# Tier 1 — count_matches
# ---------------------------------------------------------------------------


def count_matches(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    whole_word: bool = False,
    fixed_string: bool = False,
    case_sensitive: bool | str = "smart",
    path_glob: str | None = None,
    respect_gitignore: bool | None = None,
) -> dict:
    rg_ignore = respect_gitignore if respect_gitignore is not None else settings.respect_gitignore

    if _use_rg():
        from ckeditor_audit.lib.backends.ripgrep import count_matches as rg_count
        return rg_count(
            query=query,
            root=settings.project_root,
            directory=directory,
            extensions=extensions,
            settings_extensions=settings.extensions,
            settings_exclude_dirs=settings.exclude_dirs,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            fixed_string=fixed_string,
            path_glob=path_glob,
            respect_gitignore=rg_ignore,
        )

    root = settings.project_root / directory if directory else settings.project_root
    if not root.exists():
        return {"total_matches": 0, "files_matched": 0, "files_searched": 0}

    exts = tuple(e.lstrip(".") for e in extensions) if extensions else settings.extensions

    try:
        pattern = re.compile(query)
    except re.error:
        pattern = re.compile(re.escape(query))

    total_matches = 0
    files_matched = 0
    files_searched = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(settings.project_root)
        if _is_excluded(rel):
            continue
        if path.suffix.lstrip(".") not in exts:
            continue

        files_searched += 1
        file_count = 0
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    file_count += len(pattern.findall(line))
        except OSError:
            continue

        if file_count:
            total_matches += file_count
            files_matched += 1

    return {
        "total_matches": total_matches,
        "files_matched": files_matched,
        "files_searched": files_searched,
    }


# ---------------------------------------------------------------------------
# Tier 2 — find_usages
# ---------------------------------------------------------------------------


def find_usages(
    symbol: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    exclude_comments: bool = False,
    exclude_strings: bool = False,
    rank: bool = True,
) -> tuple[list[dict], int]:
    results, files_searched = grep_code(
        query=r"\b" + re.escape(symbol) + r"\b",
        directory=directory,
        extensions=extensions,
        whole_word=True,
        fixed_string=False,
    )
    if exclude_comments or exclude_strings or rank:
        from ckeditor_audit.lib.filters import annotate_matches
        from ckeditor_audit.lib.ranking import rank_results
        results = annotate_matches(results, str(settings.project_root))
        if exclude_comments:
            results = [r for r in results if not r.get("in_comment", False)]
        if exclude_strings:
            results = [r for r in results if not r.get("in_string", False)]
        if rank:
            results = rank_results(results)
    return results, files_searched


# ---------------------------------------------------------------------------
# Tier 2 — find_implementations
# ---------------------------------------------------------------------------

_IMPLEMENTS_RE = re.compile(r"\bimplements\b([^{;]+)")

# Non-anchored class-declaration scanners used to resolve the class that encloses
# an `extends`/`implements` keyword. Unlike _CLASS_PATTERN (anchored with ^ and no
# MULTILINE flag), these match anywhere in a text slice.
_CLASS_DECL_RE = re.compile(r"\b(?:class|interface|trait|enum)\s+(\w+)")
_JS_CLASS_DECL_RE = re.compile(r"\bclass\s+(\w+)")


def _enclosing_class_name(content: str, pos: int, ext: str) -> str:
    """Return the name of the class declaration nearest to (and at or before) pos."""
    prefix = content[:pos]
    rx = _CLASS_DECL_RE if ext == "php" else _JS_CLASS_DECL_RE
    last = None
    for last in rx.finditer(prefix):
        pass
    return last.group(1) if last else ""


def find_implementations(interface_name: str) -> tuple[list[dict], int]:
    if _use_ast_grep():
        from ckeditor_audit.lib.backends.astgrep import find_implementations as ag_impl
        return ag_impl(interface_name, settings.project_root, settings.exclude_dirs, settings.extensions)

    root = settings.project_root
    results: list[dict] = []
    files_searched = 0

    for path in _walk_pruning(root, ("php", "ts", "tsx")):
        ext = path.suffix.lstrip(".")
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue

        files_searched += 1
        namespace = ""

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if ext == "php":
                ns_m = _NAMESPACE_PATTERN.search(content)
                if ns_m:
                    namespace = ns_m.group(1)

            for m in _IMPLEMENTS_RE.finditer(content):
                interfaces = [i.strip().split("\\")[-1] for i in m.group(1).split(",")]
                if interface_name not in interfaces:
                    continue
                lineno = content[: m.start()].count("\n") + 1
                results.append({
                    "path": str(rel),
                    "line": lineno,
                    "class_name": _enclosing_class_name(content, m.start(), ext),
                    "namespace": namespace,
                })
        except OSError:
            continue

    return results, files_searched


# ---------------------------------------------------------------------------
# Tier 2 — find_extends
# ---------------------------------------------------------------------------

_EXTENDS_RE = re.compile(r"\bextends\s+([\w\\]+)")


def find_extends(base_class: str) -> tuple[list[dict], int]:
    if _use_ast_grep():
        from ckeditor_audit.lib.backends.astgrep import find_extends as ag_ext
        return ag_ext(base_class, settings.project_root, settings.exclude_dirs, settings.extensions)

    root = settings.project_root
    results: list[dict] = []
    files_searched = 0

    for path in _walk_pruning(root, ("php", "js", "ts", "tsx", "jsx")):
        ext = path.suffix.lstrip(".")
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue

        files_searched += 1
        namespace = ""

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if ext == "php":
                ns_m = _NAMESPACE_PATTERN.search(content)
                if ns_m:
                    namespace = ns_m.group(1)

            for m in _EXTENDS_RE.finditer(content):
                parent = m.group(1).split("\\")[-1].split("<")[0]  # strip generics
                if parent != base_class:
                    continue
                lineno = content[: m.start()].count("\n") + 1
                results.append({
                    "path": str(rel),
                    "line": lineno,
                    "class_name": _enclosing_class_name(content, m.start(), ext),
                    "namespace": namespace,
                })
        except OSError:
            continue

    return results, files_searched


# ---------------------------------------------------------------------------
# Tier 2 — find_route (Symfony PHP 8 #[Route] attributes)
# ---------------------------------------------------------------------------

_ROUTE_ATTR_RE = re.compile(r"#\[Route\(([^)]+)\)\]")
_ROUTE_METHODS_RE = re.compile(r"methods\s*:\s*\[([^\]]+)\]")


def _extract_route_path(attr_content: str) -> str | None:
    # Named parameter: path: '...' or value: '...'
    named = re.search(r"(?:path|value)\s*:\s*['\"]([^'\"]+)['\"]", attr_content)
    if named:
        return named.group(1)
    # Positional: strip named params, take first quoted string
    cleaned = re.sub(r"\w+\s*:\s*['\"][^'\"]*['\"]", "", attr_content)
    cleaned = re.sub(r"\w+\s*:\s*\[[^\]]*\]", "", cleaned)
    first = re.search(r"['\"]([^'\"]+)['\"]", cleaned)
    return first.group(1) if first else None


_ROUTE_ANNOTATION_RE = re.compile(r'@Route\s*\(\s*["\']([^"\']+)["\']')


def find_route(pattern: str) -> tuple[list[dict], int]:
    root = settings.project_root
    results: list[dict] = []
    files_searched = 0
    pattern_lower = pattern.lower()

    for path in _walk_pruning(root, ("php",)):
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue

        files_searched += 1
        current_class: str | None = None

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                file_lines = f.readlines()

            for lineno, line in enumerate(file_lines, 1):
                stripped = line.strip()

                cls_match = _CLASS_PATTERN.match(stripped)
                if cls_match:
                    current_class = cls_match.group(2)

                # PHP 8 attribute syntax: #[Route(...)]
                route_match = _ROUTE_ATTR_RE.search(stripped)
                if route_match:
                    attr_content = route_match.group(1)
                    route_path = _extract_route_path(attr_content)
                    if route_path and pattern_lower in route_path.lower():
                        methods: list[str] = []
                        methods_match = _ROUTE_METHODS_RE.search(attr_content)
                        if methods_match:
                            methods = [m.strip().strip("'\"") for m in methods_match.group(1).split(",")]
                        action = ""
                        for next_line in file_lines[lineno:lineno + 5]:
                            ns = next_line.strip()
                            if ns and not ns.startswith("#["):
                                fm = re.search(r"function\s+(\w+)", ns)
                                if fm:
                                    action = fm.group(1)
                                break
                        results.append({
                            "path": str(rel),
                            "line": lineno,
                            "route": route_path,
                            "methods": methods,
                            "class_name": current_class or "",
                            "action": action,
                            "source": "attribute",
                        })
                    continue

                # Legacy @Route annotation in docblock
                ann_match = _ROUTE_ANNOTATION_RE.search(stripped)
                if ann_match:
                    route_path = ann_match.group(1)
                    if pattern_lower in route_path.lower():
                        results.append({
                            "path": str(rel),
                            "line": lineno,
                            "route": route_path,
                            "methods": [],
                            "class_name": current_class or "",
                            "action": "",
                            "source": "annotation",
                        })

        except OSError:
            continue

    # Also search YAML routes
    yaml_results, yaml_files = find_route_yaml(pattern)
    results.extend(yaml_results)
    files_searched += yaml_files

    return results, files_searched


# ---------------------------------------------------------------------------
# find_tests (original)
# ---------------------------------------------------------------------------

def find_tests(source_path: str) -> list[dict]:
    root = settings.project_root
    results = []

    src = Path(source_path)
    stem = src.stem
    ext = src.suffix.lstrip(".")

    # PHP: replace src/ → tests/, append Test to stem
    if ext == "php":
        candidates = [
            # Direct mirror: src/Domain/X.php → tests/Domain/XTest.php
            Path(str(src).replace("src/", "tests/", 1)).with_stem(stem + "Test"),
            # Flat search by name
        ]
        for candidate in candidates:
            full = root / candidate
            if full.exists():
                results.append({"path": str(candidate), "framework": "phpunit"})

        # Fallback: rglob for *Test.php with same stem
        if not results:
            for path in root.rglob(f"{stem}Test.php"):
                rel = path.relative_to(root)
                if not _is_excluded(rel):
                    results.append({"path": str(rel), "framework": "phpunit"})

    # JS/TS: look for *.test.ts, *.spec.ts, *.test.js, *.spec.js
    elif ext in ("js", "ts", "tsx", "jsx"):
        for test_ext in (f"{stem}.test.ts", f"{stem}.spec.ts", f"{stem}.test.js", f"{stem}.spec.js", f"{stem}.test.tsx"):
            for path in root.rglob(test_ext):
                rel = path.relative_to(root)
                if not _is_excluded(rel):
                    results.append({"path": str(rel), "framework": "jest"})

        # Playwright: look in playwright/ or features/ by stem
        for path in (root / "playwright").rglob(f"*{stem}*"):
            if path.is_file() and path.suffix in (".ts", ".js"):
                rel = path.relative_to(root)
                results.append({"path": str(rel), "framework": "playwright"})

    return results


# ---------------------------------------------------------------------------
# find_source — inverse of find_tests
# ---------------------------------------------------------------------------

def find_source(test_path: str) -> list[dict]:
    root = settings.project_root
    src = Path(test_path)
    ext = src.suffix.lstrip(".")
    results = []

    if ext == "php":
        # FooTest.php → Foo.php in src/
        stem = src.stem
        if stem.endswith("Test"):
            source_stem = stem[:-4]
            candidate = Path(str(src).replace("tests/", "src/", 1)).with_stem(source_stem)
            full = root / candidate
            if full.exists():
                results.append({"path": str(candidate)})
            else:
                for path in root.rglob(f"{source_stem}.php"):
                    rel = path.relative_to(root)
                    if not _is_excluded(rel) and "test" not in str(rel).lower():
                        results.append({"path": str(rel)})
                        break

    elif ext in ("js", "ts", "tsx", "jsx"):
        # foo.test.ts → foo.ts
        for suffix in (".test", ".spec"):
            if src.stem.endswith(suffix):
                source_stem = src.stem[: -len(suffix)]
                for candidate_ext in (ext, "ts", "js"):
                    for path in root.rglob(f"{source_stem}.{candidate_ext}"):
                        rel = path.relative_to(root)
                        if not _is_excluded(rel) and ".test." not in str(rel) and ".spec." not in str(rel):
                            results.append({"path": str(rel)})

    return results


# ---------------------------------------------------------------------------
# find_definition — universal single-call definition lookup
# ---------------------------------------------------------------------------

def find_definition(name: str, kind: str | None = None) -> tuple[list[dict], int]:
    """Find the most likely definition of name (class, method, function, route)."""
    if kind in ("class", "interface", "trait", "enum", None):
        results, files = find_class(name, kind=kind)
        if results:
            return results, files

    if kind in ("method", "function", None):
        results, files = find_method(name, class_name=None)
        if results:
            return results, files

    if kind in ("route", None):
        results, files = find_route(name)
        if results:
            return results, files

    # Fallback to grep
    results, files = grep_code(name, whole_word=True, fixed_string=True)
    return results[:5], files


# ---------------------------------------------------------------------------
# who_calls / what_calls — lightweight call-site navigation
# ---------------------------------------------------------------------------

_CALL_PATTERN_TMPL = r"\b{name}\s*\("


def who_calls(
    method: str,
    class_name: str | None = None,
    directory: str | None = None,
) -> tuple[list[dict], int]:
    """Find call sites of method/function name across the project."""
    query = _CALL_PATTERN_TMPL.format(name=re.escape(method))
    results, files_searched = grep_code(query=query, directory=directory)

    # Enrich each result with the enclosing function/method name (best-effort)
    enriched = []
    for r in results:
        full_path = settings.project_root / r["path"]
        caller = _find_enclosing_function(full_path, r["line"])
        enriched.append({**r, "caller": caller})

    return enriched, files_searched


def what_calls(
    method: str,
    class_name: str | None = None,
) -> tuple[list[dict], int]:
    """Find all methods/functions called by the given method — outgoing calls from the method body."""
    # First locate the method definition
    definitions, _ = find_method(method, class_name=class_name)
    if not definitions:
        return [], 0

    defn = definitions[0]
    full_path = settings.project_root / defn["path"]
    body_start = defn["line"]
    body_end = _find_function_end(full_path, body_start)

    # Grep for call patterns in that range
    call_re = re.compile(r"\b(\w+)\s*\(")
    results: list[dict] = []
    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for lineno in range(body_start, min(body_end + 1, len(lines) + 1)):
            line = lines[lineno - 1]
            for m in call_re.finditer(line):
                name = m.group(1)
                if name not in ("if", "for", "while", "switch", "foreach", "catch", "return", "echo", "print"):
                    results.append({
                        "path": defn["path"],
                        "line": lineno,
                        "callee": name,
                        "snippet": line.strip()[:120],
                    })
    except OSError:
        pass

    return results, 1


_ENCLOSING_SKIP = frozenset(["if", "for", "while", "switch", "catch", "else", "do", "try"])

# PHP + JS/TS named functions and class methods
_ENCLOSING_FN_RE = re.compile(
    r"^\s*(?:(?:export|default|public|protected|private|static|async|abstract|final|readonly)\s+)*"
    r"(?:function\s+)?(\w+)\s*\("
)
# JS/TS arrow functions:  const foo = (...) =>  or  const foo = async (...) =>
_ENCLOSING_ARROW_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\("
)


def _find_enclosing_function(path: Path, target_line: int) -> str | None:
    """Best-effort: find the function/method name enclosing target_line (PHP + JS/TS)."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for i in range(min(target_line - 1, len(lines) - 1), -1, -1):
            line = lines[i]
            m = _ENCLOSING_FN_RE.match(line)
            if m and m.group(1) not in _ENCLOSING_SKIP:
                return m.group(1)
            m = _ENCLOSING_ARROW_RE.match(line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


def _find_function_end(path: Path, start_line: int, max_scan: int = 200) -> int:
    """Find the closing brace of the function starting at start_line (best-effort)."""
    depth = 0
    started = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for i, line in enumerate(lines[start_line - 1:start_line - 1 + max_scan], start=start_line):
            depth += line.count("{") - line.count("}")
            if depth > 0:
                started = True
            if started and depth <= 0:
                return i
    except OSError:
        pass
    return start_line + max_scan


# ---------------------------------------------------------------------------
# find_route — extended with YAML support
# ---------------------------------------------------------------------------

def find_route_yaml(pattern: str) -> tuple[list[dict], int]:
    """Search for route pattern in Symfony YAML route files (line-by-line state machine)."""
    root = settings.project_root
    results: list[dict] = []
    files_searched = 0
    pattern_lower = pattern.lower()

    config_dir = root / "config"
    if not config_dir.exists():
        return [], 0

    for path in config_dir.rglob("*.yaml"):
        rel = path.relative_to(root)
        if _is_excluded(rel):
            continue
        files_searched += 1
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        # State: current top-level route block
        route_name: str | None = None
        route_start_line: int = 0
        route_path: str | None = None
        route_methods: list[str] = []

        def _flush() -> None:
            if route_name and route_path and pattern_lower in route_path.lower():
                results.append({
                    "path": str(rel),
                    "line": route_start_line,
                    "route": route_path,
                    "methods": list(route_methods),
                    "source": "yaml",
                })

        for lineno, line in enumerate(lines, 1):
            if not line.strip() or line.strip().startswith("#"):
                continue

            # Top-level key (no leading whitespace): new route block
            if line and not line[0].isspace():
                _flush()
                route_name = None
                route_path = None
                route_methods = []
                # Match  route_name:  (bare key, may have trailing colon only)
                m = re.match(r'^([\w./-][\w./_-]*):\s*$', line)
                if m:
                    route_name = m.group(1)
                    route_start_line = lineno
                continue

            # Indented key inside a route block
            if route_name is None:
                continue
            stripped = line.strip()
            if stripped.startswith("path:"):
                route_path = stripped[5:].strip().strip("'\"")
            elif stripped.startswith("methods:"):
                # Inline list:  methods: [GET, POST]
                inline = re.search(r'\[([^\]]+)\]', stripped)
                if inline:
                    route_methods = [s.strip().strip("'\"") for s in inline.group(1).split(",") if s.strip()]
                # Scalar:  methods: GET
                else:
                    val = stripped[8:].strip().strip("'\"")
                    if val:
                        route_methods = [val]
            elif stripped.startswith("- "):
                # Sequence item under methods:
                val = stripped[2:].strip().strip("'\"")
                if val:
                    route_methods.append(val)

        _flush()

    return results, files_searched
