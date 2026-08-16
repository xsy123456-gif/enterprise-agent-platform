"""Source-import scanning helpers for architecture guard tests (Phase 18.0).

These guards analyze the module graph (via AST import scanning) rather than
importing the application, so they stay fast and side-effect free.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module_imports(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def scan_imports(relative_dir):
    """Return {relpath: set(imported_module)} for every .py under relative_dir."""
    base = ROOT / relative_dir
    result = {}
    for path in base.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        result[str(path.relative_to(ROOT))] = _module_imports(path)
    return result


def all_imports(relative_dir):
    combined = set()
    for imports in scan_imports(relative_dir).values():
        combined |= imports
    return combined


def files_matching(relative_dir, component):
    """Return paths under relative_dir whose path contains ``component``."""
    base = ROOT / relative_dir
    return [
        str(p.relative_to(ROOT))
        for p in base.rglob("*.py")
        if "__pycache__" not in p.parts
        and component in str(p.relative_to(base))
    ]
