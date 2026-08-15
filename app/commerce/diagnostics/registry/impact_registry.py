"""ImpactFormulaRegistry — versioned ImpactFormula definitions."""

from app.commerce.diagnostics.definitions.impact import ImpactFormula
from app.commerce.diagnostics.registry.base import VersionedRegistry


class ImpactFormulaRegistry(VersionedRegistry):

    def __init__(self):
        super().__init__("impact formula")

    def register(self, formula: ImpactFormula):
        return super().register(formula.formula_id, formula.version, formula)

    def get(self, formula_id, version=None) -> ImpactFormula:
        return super().get(formula_id, version)


__all__ = ["ImpactFormulaRegistry"]
