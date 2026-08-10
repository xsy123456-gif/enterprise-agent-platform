"""Structural and isolation validation for cross-Agent contracts."""

import json


DEFAULT_MAX_PAYLOAD_BYTES = 64 * 1024

SENSITIVE_KEYS = {
    "password", "passwd", "secret", "token", "api_key", "authorization",
    "cookie", "credential", "private_key",
}
RUNTIME_CONTEXT_KEYS = {
    "permission_context", "policy_context", "memory_context", "memory_policy",
    "audit_context", "runtime_state", "graph_state", "authorization_result",
    "governance_decision", "guard_result", "tool_results",
}
LANGGRAPH_PRIVATE_KEYS = {
    "_action", "_events", "pending_tool_call", "reasoning_output",
    "tool_call_request",
}
FORBIDDEN_OBJECT_MODULES = (
    "app.runtime.contracts.state",
    "app.runtime.backends.langgraph.state",
    "app.runtime.execution",
)


class AgentContractValidationError(ValueError):
    pass


def normalized_key(key):
    return str(key).strip().lower().replace("-", "_")


def is_sensitive_key(key):
    value = normalized_key(key)
    return value in SENSITIVE_KEYS or any(
        value.endswith(f"_{marker}") for marker in SENSITIVE_KEYS
    )


def validate_transfer_value(value, field_name="payload", max_bytes=None):
    _reject_forbidden(value, field_name)
    try:
        serialized = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as error:
        raise AgentContractValidationError(
            f"{field_name} must be JSON serializable"
        ) from error
    if max_bytes is not None and len(serialized.encode("utf-8")) > max_bytes:
        raise AgentContractValidationError(
            f"{field_name} exceeds maximum size of {max_bytes} bytes"
        )
    return json.loads(serialized)


def _reject_forbidden(value, path):
    value_type = type(value)
    if value_type.__module__.startswith(FORBIDDEN_OBJECT_MODULES):
        raise AgentContractValidationError(
            f"Runtime object cannot cross Agent boundary: {path}"
        )
    if callable(value):
        raise AgentContractValidationError(
            f"Callable cannot cross Agent boundary: {path}"
        )
    if isinstance(value, dict):
        normalized = {normalized_key(key) for key in value}
        private = normalized.intersection(LANGGRAPH_PRIVATE_KEYS)
        if private:
            raise AgentContractValidationError(
                f"LangGraph State fields are forbidden at {path}: {sorted(private)}"
            )
        for key, item in value.items():
            key_name = normalized_key(key)
            child_path = f"{path}.{key}"
            if is_sensitive_key(key_name):
                raise AgentContractValidationError(
                    f"Sensitive field is forbidden: {child_path}"
                )
            if key_name in RUNTIME_CONTEXT_KEYS:
                raise AgentContractValidationError(
                    f"Runtime context field is forbidden: {child_path}"
                )
            _reject_forbidden(item, child_path)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_forbidden(item, f"{path}[{index}]")


class AgentContractValidator:
    """Validates version, isolation, serializability and bounded payload size."""

    SCHEMA_VERSIONS = {
        "agent-message.v1", "agent-context.v1", "agent-invocation.v1",
        "agent-result.v1",
    }

    def __init__(self, max_payload_bytes=DEFAULT_MAX_PAYLOAD_BYTES):
        if not isinstance(max_payload_bytes, int) or max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be a positive integer")
        self.max_payload_bytes = max_payload_bytes

    def validate(self, contract):
        schema_version = getattr(contract, "schema_version", None)
        if schema_version not in self.SCHEMA_VERSIONS:
            raise AgentContractValidationError(
                f"Unsupported Agent contract schema: {schema_version}"
            )
        if not hasattr(contract, "to_dict"):
            raise AgentContractValidationError("Agent contract must support to_dict")
        validate_transfer_value(
            contract.to_dict(), contract.__class__.__name__, self.max_payload_bytes
        )
        return contract
