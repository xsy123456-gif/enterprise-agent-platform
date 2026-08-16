"""Phase 13.4 Agent Governance tests."""

from types import SimpleNamespace

import pytest

from app.platform.agent_control.domain import (
    PERM_EXECUTE,
    PERM_MANAGE,
    SUBJECT_DEPARTMENT,
    SUBJECT_USER,
)
from app.platform.agent_control.errors import AgentAccessDeniedError
from app.platform.agent_control.governance import (
    AgentAccessControl,
    AgentAccessPolicy,
)


def _finance_employee():
    return SimpleNamespace(subject_id="E100", roles=("finance_operator",),
                           department_id="finance")


def _commerce_employee():
    return SimpleNamespace(subject_id="E200", roles=("commerce_operator",),
                           department_id="marketing")


def _control():
    control = AgentAccessControl()
    control.add_policy(AgentAccessPolicy(
        policy_id="p1", agent_id="finance_agent",
        subject_type=SUBJECT_DEPARTMENT, subject_id="finance",
        permission=PERM_EXECUTE))
    control.add_policy(AgentAccessPolicy(
        policy_id="p2", agent_id="commerce_agent",
        subject_type=SUBJECT_USER, subject_id="E200",
        permission=PERM_EXECUTE))
    return control


def test_finance_employee_denied_commerce_agent():
    control = _control()
    assert control.check("commerce_agent", _finance_employee(), PERM_EXECUTE) is False
    with pytest.raises(AgentAccessDeniedError):
        control.authorize("commerce_agent", _finance_employee(), PERM_EXECUTE)


def test_department_employee_allowed_own_agent():
    control = _control()
    assert control.check("finance_agent", _finance_employee(), PERM_EXECUTE) is True


def test_permission_mismatch_denied():
    control = _control()
    assert control.check("finance_agent", _finance_employee(), PERM_MANAGE) is False


def test_default_deny_without_policy():
    control = AgentAccessControl()
    assert control.check("sales_agent", _commerce_employee(), PERM_EXECUTE) is False
