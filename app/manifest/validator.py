from app.manifest.schema import (
    ALLOWED_AGENT_FIELDS,
    ALLOWED_MEMORY_FIELDS,
    ALLOWED_TOP_LEVEL_FIELDS,
    PROHIBITED_FIELDS,
    REQUIRED_AGENT_FIELDS,
    REQUIRED_TOP_LEVEL_FIELDS,
    ManifestSchemaError,
)


class ManifestValidationError(ValueError):
    pass


class ManifestValidator:
    def __init__(
        self,
        capability_catalog,
        tool_registry,
        policy_registry,
        allowed_models=None,
    ):
        self.capability_catalog = capability_catalog
        self.tool_registry = tool_registry
        self.policy_registry = policy_registry
        self.allowed_models = set(allowed_models or {"deepseek-chat"})

    def validate(self, manifest):
        self._validate_schema(manifest)
        capabilities = self._validate_capabilities(manifest)
        self._validate_tools(manifest, capabilities)
        self._validate_policy(manifest)
        self._validate_runtime(manifest)
        return manifest

    def _validate_schema(self, manifest):
        raw = manifest.raw
        missing = REQUIRED_TOP_LEVEL_FIELDS - set(raw)
        if missing:
            raise ManifestSchemaError(
                f"Missing manifest fields: {sorted(missing)}"
            )
        unknown = set(raw) - ALLOWED_TOP_LEVEL_FIELDS
        if unknown:
            raise ManifestSchemaError(
                f"Unknown manifest fields: {sorted(unknown)}"
            )
        prohibited = self._find_prohibited_fields(raw)
        if prohibited:
            raise ManifestSchemaError(
                f"Prohibited manifest fields: {sorted(prohibited)}"
            )

        agent = raw.get("agent")
        if not isinstance(agent, dict):
            raise ManifestSchemaError("agent must be a mapping")
        missing_agent = REQUIRED_AGENT_FIELDS - set(agent)
        if missing_agent:
            raise ManifestSchemaError(
                f"Missing agent fields: {sorted(missing_agent)}"
            )
        unknown_agent = set(agent) - ALLOWED_AGENT_FIELDS
        if unknown_agent:
            raise ManifestSchemaError(
                f"Unknown agent fields: {sorted(unknown_agent)}"
            )
        owner = agent.get("owner")
        if not isinstance(owner, dict) or set(owner) != {"team"}:
            raise ManifestSchemaError("agent.owner must contain only team")
        required_values = {
            "agent.id": manifest.agent_id,
            "agent.version": manifest.version,
            "agent.name": manifest.name,
            "agent.description": manifest.description,
            "agent.owner.team": manifest.owner,
        }
        for field, value in required_values.items():
            if not isinstance(value, str) or not value.strip():
                raise ManifestSchemaError(f"{field} must be a non-empty string")
        if not isinstance(manifest.capabilities, list) or not manifest.capabilities:
            raise ManifestSchemaError("capabilities must be a non-empty list")
        if not all(isinstance(item, str) and item for item in manifest.capabilities):
            raise ManifestSchemaError("capabilities must contain strings")
        if len(manifest.capabilities) != len(set(manifest.capabilities)):
            raise ManifestSchemaError("capabilities must be unique")
        raw_tools = raw.get("tools")
        if not isinstance(raw_tools, dict) or set(raw_tools) != {"allowed"}:
            raise ManifestSchemaError("tools must contain only allowed")
        if not isinstance(manifest.tools, list) or not all(
            isinstance(item, str) and item for item in manifest.tools
        ):
            raise ManifestSchemaError("tools.allowed must contain strings")
        if len(manifest.tools) != len(set(manifest.tools)):
            raise ManifestSchemaError("tools.allowed must be unique")
        if not isinstance(manifest.memory_policy, dict):
            raise ManifestSchemaError("memory must be a mapping")
        unknown_memory = set(manifest.memory_policy) - ALLOWED_MEMORY_FIELDS
        if unknown_memory:
            raise ManifestSchemaError(
                f"Unknown memory fields: {sorted(unknown_memory)}"
            )
        for field in ALLOWED_MEMORY_FIELDS:
            values = manifest.memory_policy.get(field, [])
            if not isinstance(values, list) or not all(
                isinstance(item, str) and item for item in values
            ):
                raise ManifestSchemaError(f"memory.{field} must contain strings")
        if not isinstance(raw.get("policy"), dict):
            raise ManifestSchemaError("policy must be a mapping")
        if not isinstance(raw.get("runtime"), dict):
            raise ManifestSchemaError("runtime must be a mapping")

    def _validate_capabilities(self, manifest):
        definitions = []
        for capability_id in manifest.capabilities:
            try:
                definitions.append(self.capability_catalog.get(capability_id))
            except KeyError as error:
                raise ManifestValidationError(
                    f"Unknown capability: {capability_id}"
                ) from error
        return definitions

    def _validate_tools(self, manifest, capabilities):
        allowed_tools = {
            tool
            for capability in capabilities
            for tool in capability.allowed_tools
        }
        for tool_name in manifest.tools:
            if self.tool_registry.get(tool_name) is None:
                raise ManifestValidationError(f"Unknown tool: {tool_name}")
            if tool_name not in allowed_tools:
                raise ManifestValidationError(
                    f"Tool is not allowed by declared capabilities: {tool_name}"
                )

    def _validate_policy(self, manifest):
        if not manifest.policy_ref:
            raise ManifestValidationError("policy.ref is required")
        try:
            self.policy_registry.get_policy(manifest.policy_ref)
        except KeyError as error:
            raise ManifestValidationError(
                f"Unknown policy: {manifest.policy_ref}"
            ) from error

    def _validate_runtime(self, manifest):
        if not isinstance(manifest.runtime, dict):
            raise ManifestValidationError("runtime must be a mapping")
        model = manifest.runtime.get("model")
        if model not in self.allowed_models:
            raise ManifestValidationError(f"Unsupported runtime model: {model}")

    def _find_prohibited_fields(self, value):
        found = set()
        if isinstance(value, dict):
            for key, item in value.items():
                if key in PROHIBITED_FIELDS:
                    found.add(key)
                found.update(self._find_prohibited_fields(item))
        elif isinstance(value, list):
            for item in value:
                found.update(self._find_prohibited_fields(item))
        return found
