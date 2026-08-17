"""RuleSetRegistry — versioned RuleSet definitions."""

from app.commerce.diagnostics.definitions.rules import RuleSet
from app.commerce.diagnostics.registry.base import VersionedRegistry


class RuleSetRegistry(VersionedRegistry):

    def __init__(self):
        super().__init__("rule set")

    def register(self, rule_set: RuleSet):
        return super().register(rule_set.rule_set_id, rule_set.version, rule_set)

    def get(self, rule_set_id, version=None) -> RuleSet:
        return super().get(rule_set_id, version)


__all__ = ["RuleSetRegistry"]
