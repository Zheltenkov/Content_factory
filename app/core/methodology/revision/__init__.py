"""Human-in-the-loop methodology revision runtime."""

from app.core.methodology.revision.assistant import MethodologyAssistantCommandParser
from app.core.methodology.revision.checkpoint import (
    HumanApprovalCheckpointPolicy,
    build_checkpoint,
    build_requirement_matrix,
    checkpoint_artifact_hash,
)
from app.core.methodology.revision.contracts import (
    ChangeRequestConflict,
    HumanApprovalCheckpoint,
    MethodologistChangeRequest,
    MethodologyAssistantCommand,
    MethodologyAssistantParseContext,
    ScopedResumePlan,
    ScopedRevisionResult,
)
from app.core.methodology.revision.guards import has_hard_conflicts, validate_methodologist_change_request
from app.core.methodology.revision.repo import MethodologyRevisionRepo, create_revision_schema, default_revision_repo
from app.core.methodology.revision.scoped_revision import RevisionRejectedError, ScopedRevisionExecutor
from app.core.methodology.revision.target_registry import SectionTarget, SectionTargetRegistry, build_section_target_registry

__all__ = [
    "ChangeRequestConflict",
    "HumanApprovalCheckpoint",
    "HumanApprovalCheckpointPolicy",
    "MethodologistChangeRequest",
    "MethodologyAssistantCommand",
    "MethodologyAssistantCommandParser",
    "MethodologyAssistantParseContext",
    "MethodologyRevisionRepo",
    "RevisionRejectedError",
    "ScopedResumePlan",
    "ScopedRevisionExecutor",
    "ScopedRevisionResult",
    "SectionTarget",
    "SectionTargetRegistry",
    "build_checkpoint",
    "build_requirement_matrix",
    "build_section_target_registry",
    "checkpoint_artifact_hash",
    "create_revision_schema",
    "default_revision_repo",
    "has_hard_conflicts",
    "validate_methodologist_change_request",
]
