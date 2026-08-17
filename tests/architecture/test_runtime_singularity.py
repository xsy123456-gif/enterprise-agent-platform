"""Phase 18.0 guard: Runtime Singularity.

Only ``app/runtime/`` owns the execution lifecycle, checkpoint / durable
execution, tool execution semantics and execution recovery.  The L2-L7
"runtimes" (Agent / Collaboration / Reliability / Business Action) must not add
a parallel checkpoint or durable-execution subsystem.
"""

from tests.architecture._scan import files_matching


def test_single_checkpoint_source():
    runtime_checkpoints = files_matching("app/runtime", "checkpoint")
    assert runtime_checkpoints, "app/runtime must own the checkpoint system"
    # no parallel checkpoint/durable module outside app/runtime
    for area in ("app/commerce", "app/platform"):
        assert files_matching(area, "checkpoint") == []
        assert files_matching(area, "durable") == []


def test_single_tool_runner_source():
    assert files_matching("app/runtime", "tool_runner")
    for area in ("app/commerce", "app/platform"):
        assert files_matching(area, "tool_runner") == []


def test_platform_has_no_own_execution_engine():
    # L2-L7 must not re-implement a durable execution engine (engine.py under
    # platform is a *workflow* engine, not a durable execution engine; the guard
    # specifically forbids durable/checkpoint primitives, asserted above).
    assert files_matching("app/platform", "durable_execution") == []
