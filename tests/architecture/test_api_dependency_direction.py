"""Phase 18.12 guard: API is the outermost adapter.

The API layer depends on the platform; the platform never depends on the API.
The API layer never executes tools / plans / repository / diagnostic kernel
directly (it goes through the Product Gateway + public service ports).
"""

from tests.architecture._scan import all_imports, scan_imports

_CORE_AREAS = (
    "app/core",
    "app/runtime",
    "app/execution",
    "app/commerce/domain",
    "app/commerce/repositories",
    "app/commerce/diagnostics",
    "app/platform",
)


def test_platform_does_not_import_api():
    for area in _CORE_AREAS:
        imports = all_imports(area)
        for mod in imports:
            assert not mod.startswith("app.api"), (
                f"{area} imports the API layer {mod!r}"
            )


def test_api_does_not_execute_tools_or_plans_directly():
    forbidden = (
        "app.runtime.tool_runner",
        "app.commerce.diagnostics.plans.executor",
        "app.commerce.repositories.inmemory",
        "app.commerce.repositories.postgres",
    )
    for path, imports in scan_imports("app/api").items():
        for mod in imports:
            for prefix in forbidden:
                assert not mod.startswith(prefix), (
                    f"{path} imports forbidden boundary {mod!r}"
                )
