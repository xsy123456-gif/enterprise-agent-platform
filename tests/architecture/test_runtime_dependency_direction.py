"""Phase 18.8 guard: Runtime must not depend on the Production platform.

Foundation (``app/runtime``, ``app/execution``) is the event source; Production
Observability is the consumer.  A Foundation -> Platform dependency is
forbidden.
"""

from tests.architecture._scan import all_imports

_FOUNDATION_AREAS = ("app/runtime", "app/execution")


def test_runtime_does_not_import_production_platform():
    for area in _FOUNDATION_AREAS:
        imports = all_imports(area)
        for mod in imports:
            assert not mod.startswith("app.platform.production"), (
                f"{area} imports production platform {mod!r}"
            )
            assert not mod.startswith("app.platform.business"), (
                f"{area} imports business platform {mod!r}"
            )
            assert not mod.startswith("app.platform.intelligence"), (
                f"{area} imports intelligence platform {mod!r}"
            )
