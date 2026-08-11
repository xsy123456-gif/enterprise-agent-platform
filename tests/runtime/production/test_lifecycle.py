import pytest

from app.runtime.production import AgentLifecycleManager, AgentLifecycleState


def active_manager():
    manager = AgentLifecycleManager()
    manager.create("sales_agent")
    for state in ("registered", "validated", "active"):
        manager.transition("sales_agent", state)
    return manager


def test_complete_lifecycle_reaches_archive():
    manager = active_manager()
    manager.transition("sales_agent", "suspended")
    manager.transition("sales_agent", "deprecated")
    record = manager.transition("sales_agent", "archived")
    assert record.state is AgentLifecycleState.ARCHIVED


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("created", "active"),
        ("registered", "suspended"),
        ("validated", "deprecated"),
        ("active", "archived"),
        ("suspended", "archived"),
        ("deprecated", "active"),
        ("archived", "active"),
    ],
)
def test_invalid_lifecycle_transitions_are_rejected(source, target):
    manager = AgentLifecycleManager()
    manager.create("agent")
    path = {
        "registered": ["registered"],
        "validated": ["registered", "validated"],
        "active": ["registered", "validated", "active"],
        "suspended": ["registered", "validated", "active", "suspended"],
        "deprecated": ["registered", "validated", "active", "deprecated"],
        "archived": ["registered", "validated", "active", "deprecated", "archived"],
    }.get(source, [])
    for state in path:
        manager.transition("agent", state)
    with pytest.raises(ValueError, match="Invalid Agent lifecycle transition"):
        manager.transition("agent", target)


def test_only_active_agent_accepts_new_execution_and_binding():
    manager = active_manager()
    manager.assert_new_execution_allowed("sales_agent")
    manager.assert_new_binding_allowed("sales_agent")
    manager.transition("sales_agent", "suspended")
    with pytest.raises(PermissionError):
        manager.assert_new_execution_allowed("sales_agent")
    with pytest.raises(PermissionError):
        manager.assert_new_binding_allowed("sales_agent")


@pytest.mark.parametrize("state", ["active", "suspended", "deprecated"])
def test_existing_execution_resume_policy(state):
    manager = active_manager()
    if state == "suspended":
        manager.transition("sales_agent", state)
    elif state == "deprecated":
        manager.transition("sales_agent", state)
    manager.assert_resume_allowed("sales_agent")


def test_archived_agent_cannot_resume():
    manager = active_manager()
    manager.transition("sales_agent", "deprecated")
    manager.transition("sales_agent", "archived")
    with pytest.raises(PermissionError):
        manager.assert_resume_allowed("sales_agent")


def test_lifecycle_change_callback_receives_previous_and_current():
    changes = []
    manager = AgentLifecycleManager(lambda old, new: changes.append((old, new)))
    manager.create("agent")
    manager.transition("agent", "registered")
    assert changes[0][0] is None
    assert changes[-1][0].state is AgentLifecycleState.CREATED
    assert changes[-1][1].state is AgentLifecycleState.REGISTERED
