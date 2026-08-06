import json


class CapabilityCatalog:
    """The platform whitelist of business capabilities."""

    def __init__(self, repository):
        self.repository = repository

    def register(self, capability):
        self.repository.add(capability)
        return capability

    def get(self, capability_id):
        capability = self.repository.get(capability_id)
        if capability is None:
            raise KeyError(f"Capability not found: {capability_id}")
        return capability

    def list_capabilities(self):
        return self.repository.list()

    def get_catalog_context(self):
        # Planning gets business semantics only; tool bindings and governance
        # metadata stay in the deterministic control layer.
        return [
            {
                "capability_id": capability.capability_id,
                "name": capability.name,
                "description": capability.description,
                "examples": list(capability.examples),
            }
            for capability in self.list_capabilities()
        ]

    def format_catalog_context(self):
        return json.dumps(
            self.get_catalog_context(),
            ensure_ascii=False,
            indent=2,
        )
