from pathlib import Path

import yaml

from app.manifest.loader import ManifestLoader
from app.manifest.parser import ManifestParser
from app.manifest.validator import ManifestValidator
from app.sources.builtin import BuiltinAgentSource
from app.sources.git import GitAgentSource


class AgentSourceConfigurationError(ValueError):
    pass


class AgentSourceFactory:
    def __init__(self, llm, catalog, tool_registry, agent_registry):
        self.llm = llm
        self.catalog = catalog
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry

    def create(self, config):
        if not isinstance(config, dict):
            raise AgentSourceConfigurationError(
                "Agent Source configuration must be a mapping"
            )
        source_config = config.get("agent_source", config)
        if not isinstance(source_config, dict):
            raise AgentSourceConfigurationError(
                "agent_source configuration must be a mapping"
            )
        source_type = source_config.get("type")
        if source_type == "builtin":
            return BuiltinAgentSource(
                llm=self.llm,
                catalog=self.catalog,
                tool_registry=self.tool_registry,
            )
        if source_type == "git":
            repo_path = source_config.get("path")
            if not isinstance(repo_path, str) or not repo_path.strip():
                raise AgentSourceConfigurationError(
                    "Git Agent Source requires a repository path"
                )
            parser = ManifestParser()
            validator = ManifestValidator(
                capability_catalog=self.catalog,
                tool_registry=self.tool_registry,
                policy_registry=self.agent_registry,
            )
            loader = ManifestLoader(
                parser=parser,
                validator=validator,
                registry=self.agent_registry,
                llm=self.llm,
            )
            return GitAgentSource(
                repo_path=repo_path,
                parser=parser,
                validator=validator,
                loader=loader,
            )
        raise AgentSourceConfigurationError(
            f"Unsupported Agent Source type: {source_type}"
        )

    def create_from_file(self, path):
        config_path = Path(path)
        try:
            with config_path.open("r", encoding="utf-8") as stream:
                config = yaml.safe_load(stream)
        except (OSError, yaml.YAMLError) as error:
            raise AgentSourceConfigurationError(
                f"Unable to read Agent Source configuration: {path}"
            ) from error
        return self.create(config or {})
