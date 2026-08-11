import ast
from pathlib import Path


PRODUCTION_ROOT = Path("app/runtime/production")
FORBIDDEN_PREFIXES = (
    "app.memory",
    "app.runtime.backends.langgraph",
    "app.runtime.loop",
    "app.runtime.tool_runner",
    "app.runtime.multi_agent.scheduler",
    "app.runtime.recovery",
    "app.manifest",
    "app.registry",
)


def test_production_control_plane_does_not_depend_on_frozen_runtime_domains():
    violations = []
    for path in PRODUCTION_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = [node.module]
            else:
                continue
            for imported in imports:
                if imported.startswith(FORBIDDEN_PREFIXES):
                    violations.append(f"{path}:{imported}")
    assert violations == []
