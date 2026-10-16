"""Stdlib-сканер статики проекта (maintenance-аудит 2026-10-16).

Отчёт (не gate): unused imports, except/pass, requests без timeout, URL-инвентарь.
Обязательный gate правок — `python -m pytest -q`. Внешние линтеры
(pyflakes/mypy) не введены (изменение dev-зависимостей — отдельным решением).

Usage:
  python tools/static_scan.py [PATH ...]      # default: aeon/
"""

import ast
import re
import sys
from pathlib import Path

URL_RE = re.compile(r'https?://[^\s\'"\)]+')


def iter_files(targets):
    for root in targets:
        path = Path(root)
        if path.is_file() and path.suffix == ".py":
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.py"))


def scan_unused_imports(path, tree):
    if path.name == "__init__.py":
        return []  # реэкспорт-поверхность пакета: импорты — публичный API
    lines = path.read_text(encoding="utf-8").splitlines()
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.asname or alias.name).split(".")[0]
                line_text = lines[node.lineno - 1]
                if "noqa" in line_text:
                    continue  # документированный реэкспорт (facade)
                imported[name] = node.lineno
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for alias in node.names:
                line_text = lines[node.lineno - 1]
                if "noqa" in line_text:
                    continue
                imported[alias.asname or alias.name] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    # публичные реэкспорты: имена из __all__ = [...] (Str-константы)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__"
                for t in node.targets):
            used |= {e.value for e in ast.walk(node)
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return [(path, line, name) for name, line in imported.items()
            if name not in used and name != "*"]


def scan_except_pass(path, tree):
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            body = [b for b in node.body
                    if not (isinstance(b, ast.Expr)
                            and isinstance(b.value, ast.Constant))]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                hits.append((path, node.lineno))
    return hits


def scan_requests_timeout(path, tree):
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("get", "post", "head", "request",
                                       "put", "delete")):
            root = node.func.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id == "requests":
                if not any(k.arg == "timeout" for k in node.keywords):
                    hits.append((path, node.lineno))
    return hits


def main(argv=None):
    targets = argv or ["aeon"]
    unused, except_pass, no_timeout, urls = [], [], [], {}
    for path in iter_files(targets):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            print(f"SYNTAX ERROR: {path}: {exc}")
            continue
        unused += scan_unused_imports(path, tree)
        except_pass += scan_except_pass(path, tree)
        no_timeout += scan_requests_timeout(path, tree)
        for number, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            for match in URL_RE.finditer(line):
                urls.setdefault(match.group(0).split("/")[2], (path, number))

    print("== unused imports ==")
    for path, line, name in unused:
        print(f"  {path}:{line}: {name}")
    if not unused:
        print("  none")

    print("== except -> pass ==")
    for path, line in except_pass:
        print(f"  {path}:{line}")
    if not except_pass:
        print("  none")

    print("== requests.* без timeout (только прямой requests.*) ==")
    for path, line in no_timeout:
        print(f"  {path}:{line}")
    if not no_timeout:
        print("  none")

    print("== URL-инвентарь (host -> первое вхождение) ==")
    for host in sorted(urls):
        path, line = urls[host]
        print(f"  {host:32} {path}:{line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
