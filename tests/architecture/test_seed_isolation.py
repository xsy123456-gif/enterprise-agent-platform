"""Phase 18.14 guard: platform never reads the seed business world directly.

The seed data lives under ``data/seed/`` and is consumed only by the simulation
services (via ``SimulationStateLoader``).  The platform and its connectors reach
that data exclusively over the external HTTP boundary.
"""

from tests.architecture._scan import scan_imports


def test_application_does_not_import_seed_tooling():
    for path, imports in scan_imports("app").items():
        for mod in imports:
            assert mod != "tools" and not mod.startswith("tools."), (
                f"{path} imports seed tooling {mod!r}; the platform must not "
                f"import the seed generator/validator"
            )


def test_connectors_do_not_import_seed_or_simulation():
    for path, imports in scan_imports("app/commerce/integration/connectors").items():
        for mod in imports:
            assert mod != "simulation" and not mod.startswith("simulation."), (
                f"{path} imports simulation {mod!r}; connectors must be HTTP-only"
            )
            assert mod != "tools" and not mod.startswith("tools."), (
                f"{path} imports seed tooling {mod!r}"
            )
