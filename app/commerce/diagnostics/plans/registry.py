"""DiagnosticPlanRegistry — versioned plans with a lifecycle.

Plan identity is ``(plan_id, version)``.  A plan moves through
DRAFT -> VALIDATED -> ACTIVE; activation compiles it (pinning all definition
references to explicit versions) and records the checksum.  Only the ACTIVE
version runs; compiled IRs are kept for historical replay so a replayed plan
never drifts with the active version of its dependencies.
"""

from app.commerce.diagnostics.errors import (
    DuplicateDefinitionError,
    UnknownDefinitionError,
    UnknownDefinitionVersionError,
)
from app.commerce.diagnostics.plans.compiler import PlanCompiler
from app.commerce.diagnostics.plans.schema import (
    PLAN_ACTIVE,
    PLAN_DEPRECATED,
    PLAN_DISABLED,
    PLAN_DRAFT,
    PLAN_VALIDATED,
)
from app.commerce.diagnostics.plans.validator import validate_plan


class DiagnosticPlanRegistry:

    def __init__(self, compile_context):
        self.compile_context = compile_context
        self.compiler = PlanCompiler()
        self._definitions = {}
        self._status = {}
        self._compiled = {}
        self._active = {}

    def register(self, plan_definition):
        validate_plan(plan_definition)
        key = (plan_definition.plan_id, plan_definition.version)
        if key in self._definitions:
            raise DuplicateDefinitionError(
                f"plan {plan_definition.plan_id!r} version "
                f"{plan_definition.version!r} is already registered"
            )
        self._definitions[key] = plan_definition
        self._status[key] = PLAN_DRAFT
        return plan_definition

    def validate(self, plan_id, version=None):
        version = self._resolve_version(plan_id, version)
        definition = self._definitions[(plan_id, version)]
        validate_plan(definition)
        self._status[(plan_id, version)] = PLAN_VALIDATED
        return definition

    def activate(self, plan_id, version=None):
        version = self._resolve_version(plan_id, version)
        definition = self._definitions[(plan_id, version)]
        ir = self.compiler.compile(definition, self.compile_context)
        self._compiled[(plan_id, version)] = ir
        self._status[(plan_id, version)] = PLAN_ACTIVE
        self._active[plan_id] = version
        return ir

    def deprecate(self, plan_id, version=None):
        version = self._resolve_version(plan_id, version)
        self._status[(plan_id, version)] = PLAN_DEPRECATED

    def disable(self, plan_id, version=None):
        version = self._resolve_version(plan_id, version)
        self._status[(plan_id, version)] = PLAN_DISABLED

    def status(self, plan_id, version=None):
        version = self._resolve_version(plan_id, version)
        return self._status[(plan_id, version)]

    def get_definition(self, plan_id, version=None):
        version = self._resolve_version(plan_id, version)
        return self._definitions[(plan_id, version)]

    def get_active_ir(self, plan_id):
        version = self._active.get(plan_id)
        if version is None:
            raise UnknownDefinitionError(f"plan {plan_id!r} is not active")
        if self._status[(plan_id, version)] != PLAN_ACTIVE:
            raise UnknownDefinitionError(
                f"plan {plan_id!r}@{version} is not ACTIVE "
                f"({self._status[(plan_id, version)]})"
            )
        return self._compiled[(plan_id, version)]

    def get_ir(self, plan_id, version=None):
        """Return the compiled IR for a (possibly historical) version."""
        version = self._resolve_version(plan_id, version)
        ir = self._compiled.get((plan_id, version))
        if ir is None:
            raise UnknownDefinitionError(
                f"plan {plan_id!r}@{version} is not compiled"
            )
        return ir

    def active_version(self, plan_id):
        return self._active.get(plan_id)

    def versions(self, plan_id):
        return sorted(version for (pid, version) in self._definitions if pid == plan_id)

    def _resolve_version(self, plan_id, version):
        if version is not None:
            if (plan_id, version) not in self._definitions:
                raise UnknownDefinitionVersionError(
                    f"plan {plan_id!r} has no version {version!r}"
                )
            return version
        active = self._active.get(plan_id)
        if active is not None:
            return active
        versions = self.versions(plan_id)
        if not versions:
            raise UnknownDefinitionError(f"plan {plan_id!r} is not registered")
        return versions[0]


__all__ = ["DiagnosticPlanRegistry"]
