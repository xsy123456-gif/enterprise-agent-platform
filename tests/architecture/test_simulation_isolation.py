"""Phase 18.13 guard: platform never imports the simulation world.

``simulation`` is an external dependency.  The platform talks to it over HTTP —
never by importing it.  This guard scans every ``app/**`` module and asserts no
``simulation`` import edge exists.
"""

from tests.architecture._scan import scan_imports


def test_platform_does_not_import_simulation():
    for path, imports in scan_imports("app").items():
        for mod in imports:
            assert mod != "simulation" and not mod.startswith("simulation."), (
                f"{path} imports the simulation world {mod!r}; the platform must "
                f"reach external systems over HTTP only"
            )


def test_production_does_not_use_simulation_base_urls_by_default():
    # No production composition may hardcode a localhost simulation base URL.
    for path, imports in scan_imports("app/composition").items():
        for mod in imports:
            assert not mod.startswith("simulation"), (
                f"{path} imports {mod!r}; composition must inject simulation "
                f"connectors via config, not import the simulation package"
            )
