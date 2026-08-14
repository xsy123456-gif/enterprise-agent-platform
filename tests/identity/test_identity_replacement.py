"""Identity replaceability + dependency boundary tests."""

import ast
from pathlib import Path

from app.identity import build_identity

from tests.identity.test_identity_validation import (
    FakeIdentityProvider,
    _base_entities,
    _user,
)


def test_fake_provider_replaces_local_file_provider():
    user = _user()
    entities = _base_entities("company_A")
    provider = FakeIdentityProvider(users={user.user_id: user}, **entities)

    system = build_identity(provider=provider)
    context = system.build_access_context("U1")
    assert context.user_id == "U1"
    assert context.department_id == "operations"
    assert context.identity_version


def _identity_imports():
    root = Path(__file__).resolve().parents[2] / "app" / "identity"
    imports = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    return imports


def test_identity_does_not_import_other_domains():
    forbidden = (
        "app.knowledge", "app.memory", "app.tools", "app.agents",
        "app.permission", "app.governance", "app.runtime",
    )
    for name in _identity_imports():
        assert not name.startswith(forbidden), f"identity imports {name}"
