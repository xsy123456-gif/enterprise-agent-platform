"""Dependency boundary tests for the security integration layer."""

import ast
from pathlib import Path


def _imports(root):
    found = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    return found


def test_identity_does_not_import_security_or_permission():
    root = Path(__file__).resolve().parents[2] / "app" / "identity"
    for name in _imports(root):
        assert not name.startswith(("app.integrations.security", "app.permission")), name


def test_permission_does_not_import_identity_or_security():
    root = Path(__file__).resolve().parents[2] / "app" / "permission"
    for name in _imports(root):
        assert not name.startswith(("app.integrations.security", "app.identity")), name


def test_integration_may_import_identity_permission_governance():
    root = Path(__file__).resolve().parents[2] / "app" / "integrations" / "security"
    for name in _imports(root):
        if not name.startswith("app."):
            continue  # stdlib / third-party
        if name.startswith("app.integrations.security"):
            continue  # own package internals
        if name.startswith((
            "app.identity", "app.permission", "app.governance",
            "app.runtime.governance",  # GovernanceGate interface (read-only)
        )):
            continue  # allowed cross-domain imports
        raise AssertionError(f"integration imports disallowed domain {name}")
