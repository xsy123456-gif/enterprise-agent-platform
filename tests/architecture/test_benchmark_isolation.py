"""Phase 18.15 guard: benchmark ground truth is physically isolated.

The platform and the simulation never import the benchmark tooling or ground
truth; the product API exposes no benchmark/ground-truth endpoint.  The
benchmark is an external observer only.
"""

from pathlib import Path

from tests.architecture._scan import scan_imports


def test_application_does_not_import_benchmark():
    for path, imports in scan_imports("app").items():
        for mod in imports:
            assert mod != "benchmark" and not mod.startswith("benchmark."), (
                f"{path} imports benchmark {mod!r}"
            )
            assert mod != "tools.benchmark" and not mod.startswith("tools.benchmark."), (
                f"{path} imports benchmark tooling {mod!r}"
            )


def test_simulation_does_not_read_ground_truth():
    for path, imports in scan_imports("simulation").items():
        for mod in imports:
            assert mod != "benchmark" and not mod.startswith("benchmark."), (
                f"{path} imports benchmark {mod!r}"
            )
            assert not mod.startswith("tools.benchmark"), (
                f"{path} imports benchmark tooling {mod!r}"
            )


def test_product_api_exposes_no_benchmark_endpoint():
    root = Path(__file__).resolve().parents[2]
    for path in (root / "app" / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("/benchmark", "/ground-truth", "/v1/debug"):
            assert forbidden not in text, f"{path.name} exposes {forbidden!r}"
