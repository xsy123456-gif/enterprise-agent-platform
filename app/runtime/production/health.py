from .models import AgentHealthReport, AgentHealthStatus, ArtifactBinding


class AgentHealthManager:
    """Read-only dependency probes for a deployed Agent binding."""

    def __init__(
        self,
        artifact_repository,
        *,
        backend_probe=None,
        tool_registry=None,
        governance_probe=None,
        on_change=None,
    ):
        self.artifact_repository = artifact_repository
        self.backend_probe = backend_probe
        self.tool_registry = tool_registry
        self.governance_probe = governance_probe
        self._last_status = {}
        self._on_change = on_change

    def check(
        self,
        agent_id: str,
        binding: ArtifactBinding,
        required_tools=(),
        warnings=(),
    ) -> AgentHealthReport:
        checks = {}
        reasons = []
        artifact = self.artifact_repository.get(binding.artifact_id)
        checks["artifact"] = bool(
            artifact is not None
            and getattr(artifact, "artifact_hash", None) == binding.artifact_hash
        )
        if not checks["artifact"]:
            reasons.append("artifact_missing_or_hash_mismatch")

        checks["backend"] = self._probe(self.backend_probe, artifact)
        if not checks["backend"]:
            reasons.append("backend_unavailable")

        checks["governance"] = self._probe(self.governance_probe, agent_id)
        if not checks["governance"]:
            reasons.append("governance_unavailable")

        invalid_tools = tuple(
            name for name in required_tools
            if self.tool_registry is None or self.tool_registry.get(name) is None
        )
        checks["tools"] = not invalid_tools
        if invalid_tools:
            reasons.append(f"invalid_tool_binding:{','.join(invalid_tools)}")

        warnings = tuple(str(item) for item in warnings if str(item))
        reasons.extend(warnings)
        status = (
            AgentHealthStatus.UNAVAILABLE
            if not all(checks.values())
            else AgentHealthStatus.WARNING if warnings
            else AgentHealthStatus.HEALTHY
        )
        report = AgentHealthReport(
            agent_id=agent_id, status=status, checks=checks, reasons=tuple(reasons)
        )
        previous = self._last_status.get(agent_id)
        self._last_status[agent_id] = report.status
        if previous != report.status and self._on_change is not None:
            self._on_change(previous, report)
        return report

    @staticmethod
    def _probe(probe, value):
        if probe is None:
            return True
        try:
            return bool(probe(value))
        except Exception:
            return False
