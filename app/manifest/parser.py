from pathlib import Path

import yaml

from app.manifest.models import AgentManifest


class ManifestParseError(ValueError):
    pass


class ManifestParser:
    """Converts YAML into an AgentManifest without platform validation."""

    def parse(self, path):
        manifest_path = Path(path)
        try:
            with manifest_path.open("r", encoding="utf-8") as stream:
                data = yaml.safe_load(stream)
        except (OSError, yaml.YAMLError) as error:
            raise ManifestParseError(f"Unable to parse manifest: {path}") from error
        return self.parse_data(data)

    def parse_data(self, data):
        if not isinstance(data, dict):
            raise ManifestParseError("Manifest root must be a mapping")

        agent = data.get("agent") or {}
        if not isinstance(agent, dict):
            raise ManifestParseError("agent must be a mapping")
        owner = agent.get("owner")
        if isinstance(owner, dict):
            owner = owner.get("team")

        tools = data.get("tools") or {}
        if isinstance(tools, dict):
            tools = tools.get("allowed") or []

        memory = data.get("memory") or {}
        policy = data.get("policy") or {}
        runtime = data.get("runtime") or {}
        return AgentManifest(
            agent_id=agent.get("id"),
            version=str(agent["version"]) if agent.get("version") is not None else None,
            name=agent.get("name"),
            description=agent.get("description"),
            owner=owner,
            capabilities=data.get("capabilities") or [],
            tools=tools,
            memory_policy=memory,
            policy_ref=policy.get("ref") if isinstance(policy, dict) else None,
            runtime=runtime,
            raw=data,
        )
