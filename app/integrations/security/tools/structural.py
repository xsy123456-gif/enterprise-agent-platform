"""Structural-only permission for ToolRunner.

User authorization moved up to ``ExecutionSecurityGate`` (Permission ->
Governance).  ToolRunner retains only structural constraints (Agent
allowed_tools, capability binding, input validation).
"""


class StructuralPermission:
    """No user-permission decision; returns allow for the structural layer."""

    def check(self, role, tool):
        return True
