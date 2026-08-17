"""Optimization subpackage (Phase 17.2)."""

from app.platform.intelligence.optimization.analyzer import (
    DetectedIssue,
    PatternDetector,
)
from app.platform.intelligence.optimization.generator import OptimizationGenerator
from app.platform.intelligence.optimization.proposal import OptimizationProposal

__all__ = ["OptimizationProposal", "DetectedIssue", "PatternDetector",
           "OptimizationGenerator"]
