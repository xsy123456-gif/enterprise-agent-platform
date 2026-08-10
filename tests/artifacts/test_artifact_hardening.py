from dataclasses import replace

import pytest

from app.artifacts import (
    ArtifactDependencySnapshot, CompiledAgentArtifact, InMemoryArtifactRepository,
)
from app.compiler.backend import CurrentBackendCompiler
from app.compiler.backend.langgraph import LangGraphBackendCompiler
from app.compiler.models import AgentGraphIR, EdgeIR, NodeIR, NodeType
from app.storage.exceptions import ConflictError


def graph():
    return AgentGraphIR(
        "sales", "1", (NodeIR("start", NodeType.START), NodeIR("end", NodeType.END)),
        (EdgeIR("start", "end"),), {}, {},
    )


def snapshot(prompt_hash="p1", tool_version="1"):
    return ArtifactDependencySnapshot(
        prompt_refs=({"path": "prompts/system.md", "hash": prompt_hash},),
        tool_bindings=({"tool_id": "crm_query", "version": tool_version,
                        "permission": "crm.customer.read"},),
        capabilities=("customer_analysis",),
        model_binding={"provider": "deepseek", "model": "deepseek-chat",
                       "config_version": "default-v1"},
    ).to_dict()


def test_compiled_artifact_hash_is_stable_and_dependency_sensitive():
    first = CompiledAgentArtifact.from_ir(graph(), "v1", snapshot())
    second = CompiledAgentArtifact.from_ir(graph(), "v1", snapshot())
    prompt_changed = CompiledAgentArtifact.from_ir(graph(), "v1", snapshot("p2"))
    tool_changed = CompiledAgentArtifact.from_ir(graph(), "v1", snapshot("p1", "2"))
    assert first.artifact_hash == second.artifact_hash
    assert first.artifact_hash != prompt_changed.artifact_hash
    assert first.artifact_hash != tool_changed.artifact_hash


def test_backend_hashes_share_ir_but_differ_by_backend():
    current = CurrentBackendCompiler().compile(graph())
    langgraph = LangGraphBackendCompiler().compile(graph())
    assert current.graph_ir_hash == langgraph.graph_ir_hash
    assert current.artifact_hash != langgraph.artifact_hash


def test_repository_is_idempotent_by_hash_and_rejects_identity_conflict():
    repository = InMemoryArtifactRepository()
    artifact = LangGraphBackendCompiler().compile(graph())
    assert repository.save(artifact) is artifact
    assert repository.save(artifact) is artifact
    assert repository.get_by_hash(artifact.artifact_hash) is artifact
    assert repository.exists(artifact.artifact_hash)
    other = LangGraphBackendCompiler(backend_version="2").compile(graph())
    conflicting = replace(other, artifact_id=artifact.artifact_id)
    with pytest.raises(ConflictError, match="identity conflict"):
        repository.save(conflicting)


def test_sensitive_dependency_data_is_rejected_but_references_are_allowed():
    with pytest.raises(ValueError, match="Sensitive artifact field"):
        ArtifactDependencySnapshot(model_binding={"api_key": "secret"})
    allowed = ArtifactDependencySnapshot(
        model_binding={"credential_ref": "deepseek/default"}
    )
    assert allowed.model_binding["credential_ref"] == "deepseek/default"
