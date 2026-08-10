"""Compilation contracts for turning AgentDefinitions into portable graph IR.

This package intentionally has no dependency on a graph runtime.  A future
runtime adapter (for example LangGraph) consumes the artifact produced here.
"""

from app.compiler.compiler import GraphCompiler
from app.compiler.models import AgentGraphIR, CompileInput, EdgeIR, NodeIR

__all__ = ["AgentGraphIR", "CompileInput", "EdgeIR", "GraphCompiler", "NodeIR"]
