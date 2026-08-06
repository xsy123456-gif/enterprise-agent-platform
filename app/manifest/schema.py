REQUIRED_TOP_LEVEL_FIELDS = {"agent", "capabilities", "tools", "policy", "runtime"}
ALLOWED_TOP_LEVEL_FIELDS = REQUIRED_TOP_LEVEL_FIELDS | {"memory"}
REQUIRED_AGENT_FIELDS = {"id", "version", "name", "description", "owner"}
ALLOWED_AGENT_FIELDS = REQUIRED_AGENT_FIELDS
ALLOWED_MEMORY_FIELDS = {"read", "write"}
PROHIBITED_FIELDS = {"status", "permissions", "admin"}


class ManifestSchemaError(ValueError):
    pass
