import pytest

from app.runtime.multi_agent import GraphExecutionPolicy


def test_graph_policy_only_controls_execution_shape():
    policy = GraphExecutionPolicy(max_parallelism=2, continue_on_failure=True)
    assert policy.max_parallelism == 2
    assert policy.continue_on_failure is True


def test_graph_policy_rejects_invalid_parallelism():
    with pytest.raises(ValueError):
        GraphExecutionPolicy(max_parallelism=0)
