"""DiagnosticPlanRegistry lifecycle tests."""

import pytest

from app.commerce.diagnostics.errors import (
    DuplicateDefinitionError,
    UnknownDefinitionError,
)
from app.commerce.diagnostics.plans import (
    PLAN_ACTIVE,
    PLAN_DRAFT,
    PLAN_VALIDATED,
)
from tests.commerce_diagnostic_plans.conftest import make_conversion_plan


def test_lifecycle_draft_validated_active(plan_registry):
    plan_registry.register(make_conversion_plan())
    assert plan_registry.status("conversion_decline_mini") == PLAN_DRAFT
    plan_registry.validate("conversion_decline_mini")
    assert plan_registry.status("conversion_decline_mini") == PLAN_VALIDATED
    ir = plan_registry.activate("conversion_decline_mini")
    assert plan_registry.status("conversion_decline_mini") == PLAN_ACTIVE
    assert ir.checksum
    assert plan_registry.get_active_ir("conversion_decline_mini").checksum == ir.checksum


def test_duplicate_registration_rejected(plan_registry):
    plan_registry.register(make_conversion_plan())
    with pytest.raises(DuplicateDefinitionError):
        plan_registry.register(make_conversion_plan())


def test_only_active_runs(plan_registry):
    plan_registry.register(make_conversion_plan())
    with pytest.raises(UnknownDefinitionError):
        plan_registry.get_active_ir("conversion_decline_mini")
    plan_registry.activate("conversion_decline_mini")
    assert plan_registry.get_active_ir("conversion_decline_mini")


def test_disable_blocks_active_execution(plan_registry):
    plan_registry.register(make_conversion_plan())
    plan_registry.activate("conversion_decline_mini")
    plan_registry.disable("conversion_decline_mini")
    with pytest.raises(UnknownDefinitionError):
        plan_registry.get_active_ir("conversion_decline_mini")


def test_historical_ir_kept_for_replay(plan_registry):
    plan_registry.register(make_conversion_plan())
    ir = plan_registry.activate("conversion_decline_mini")
    plan_registry.deprecate("conversion_decline_mini")
    # Historical replay still returns the compiled IR.
    assert plan_registry.get_ir("conversion_decline_mini", "1.0").checksum == ir.checksum
