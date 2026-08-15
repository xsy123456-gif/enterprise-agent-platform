"""Plan parser — converts a declarative dict into a ``PlanDefinition``."""

from app.commerce.diagnostics.plans.schema import PlanDefinition
from app.commerce.diagnostics.plans.validator import validate_plan


def parse_plan(data) -> PlanDefinition:
    """Parse a declarative plan dict (or pass through a ``PlanDefinition``)."""
    if isinstance(data, PlanDefinition):
        definition = data
    else:
        definition = PlanDefinition.from_dict(data)
    validate_plan(definition)
    return definition


__all__ = ["parse_plan"]
