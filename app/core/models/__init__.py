"""Shared domain contracts for the consolidated content factory."""

from app.core.models.artifacts import ArtifactRef
from app.core.models.competency import (
    BLOOM_RANK,
    BloomLevel,
    Competency,
    CompetencyEdge,
    CompetencyIndicator,
    CompetencyRef,
    EvidenceSource,
)
from app.core.models.context import MethodologyContext, ProfilePackage
from app.core.models.curriculum import ProjectSummary, UPBlock, UPProject, UPSkeleton
from app.core.models.methodology import DocImage, GeneratedDoc, RuleIssue, Severity

__all__ = [
    "BLOOM_RANK",
    "ArtifactRef",
    "BloomLevel",
    "Competency",
    "CompetencyEdge",
    "CompetencyIndicator",
    "CompetencyRef",
    "DocImage",
    "EvidenceSource",
    "GeneratedDoc",
    "MethodologyContext",
    "ProfilePackage",
    "ProjectSummary",
    "RuleIssue",
    "Severity",
    "UPBlock",
    "UPProject",
    "UPSkeleton",
]
