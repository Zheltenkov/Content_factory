"""Generator orchestration contracts shared by engine, service and API layers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StageStatus = Literal["success", "skipped", "error"]
WorkflowStatus = Literal["created", "running", "completed", "failed", "needs_review"]


def utc_now() -> datetime:
    """Return a JSON-safe UTC timestamp for workflow snapshots."""
    return datetime.now(UTC).replace(tzinfo=None)


class StageContract(BaseModel):
    """Compact runtime contract for one generator node."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    title: str
    kind: str = "generation"
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    prompt_id: str = "deterministic"
    prompt_version: str = "v1"
    model_role: str = "none"
    validators: tuple[str, ...] = ()
    repair_policy: str = "none"
    fallback_policy: str = "fail-fast"
    observability_tags: tuple[str, ...] = ("workflow", "deterministic")

    def trace_metadata(self) -> dict[str, Any]:
        """Return stable metadata for traces and workflow checkpoints."""
        return self.model_dump(mode="json")


class WorkflowCapabilities(BaseModel):
    """Feature flags exposed to UI/runtime consumers."""

    model_config = ConfigDict(extra="forbid")

    project_regeneration: bool = True
    section_regeneration: bool = True
    methodology_assistant: bool = False
    stage_review: bool = False
    final_readme_editing: bool = True
    checklist_editing: bool = True


class WorkflowProfile(BaseModel):
    """Serializable workflow mode contract."""

    model_config = ConfigDict(extra="forbid")

    id: str = "standard"
    title: str = "Standard"
    stages: tuple[str, ...] = ()
    capabilities: WorkflowCapabilities = Field(default_factory=WorkflowCapabilities)


class StageExecution(BaseModel):
    """Result of one engine stage attempt."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    node_id: str
    stage_name: str
    checkpoint_index: int
    status: StageStatus
    duration_ms: float = 0.0
    input_hash: str
    output_keys: list[str] = Field(default_factory=list)
    output_artifact: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    review_status: str | None = None
    human_review_required: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowSnapshot(BaseModel):
    """In-memory durable workflow snapshot for one generator run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    user_id: str | None = None
    status: WorkflowStatus = "created"
    current_node: str | None = None
    last_completed_node: str | None = None
    progress_current: int = 0
    progress_total: int = 0
    error: str | None = None
    checkpoints: list[StageExecution] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def start(self, total_nodes: int) -> None:
        """Mark the workflow as active."""
        self.status = "running"
        self.progress_total = max(0, int(total_nodes))
        self.updated_at = utc_now()

    def node_started(self, node_id: str, checkpoint_index: int) -> None:
        """Record the active node and progress."""
        self.status = "running"
        self.current_node = node_id
        self.progress_current = max(0, int(checkpoint_index) - 1)
        self.updated_at = utc_now()

    def node_completed(self, execution: StageExecution) -> None:
        """Attach a checkpoint emitted by the stage runner."""
        self.checkpoints.append(execution)
        self.current_node = None
        self.last_completed_node = execution.node_id
        self.progress_current = max(self.progress_current, execution.checkpoint_index)
        self.updated_at = utc_now()

    def complete(self, *, needs_review: bool = False) -> None:
        """Finalize the workflow after all executable stages."""
        self.status = "needs_review" if needs_review else "completed"
        self.current_node = None
        self.progress_current = self.progress_total
        self.updated_at = utc_now()

    def fail(self, error: str) -> None:
        """Finalize the workflow as failed."""
        self.status = "failed"
        self.current_node = None
        self.error = error
        self.updated_at = utc_now()


GENERATOR_STAGE_CONTRACTS: dict[str, StageContract] = {
    "context": StageContract(
        node_id="context",
        title="Intent & Context",
        kind="context",
        outputs=("seed", "context_meta", "context_analysis", "warnings"),
        prompt_id="context.config",
        validators=("CurriculumContext", "Project seed preflight"),
        fallback_policy="build seed from persisted curriculum context",
        observability_tags=("workflow", "context", "deterministic", "curriculum"),
    ),
    "task_planning": StageContract(
        node_id="task_planning",
        title="Task Planner",
        kind="planner",
        inputs=("seed", "context_meta", "context_analysis"),
        outputs=("task_plan", "story_map_contract", "practice_plan_contract", "artifact_chain_plan"),
        prompt_id="task_planner.config",
        validators=("TaskPlan", "planning contracts"),
        repair_policy="clamp task count and rebuild contracts deterministically",
        fallback_policy="default task plan when planning fails",
        observability_tags=("workflow", "planning", "deterministic", "contracts"),
    ),
    "title_annotation": StageContract(
        node_id="title_annotation",
        title="Title & Annotation",
        inputs=("seed", "context_meta"),
        outputs=("title", "annotation"),
        prompt_id="generator.title_annotation",
        model_role="planner",
        validators=("title length", "annotation structure"),
        repair_policy="retry typed title/annotation once",
        fallback_policy="deterministic title from curriculum project",
        observability_tags=("workflow", "generation", "llm", "title", "annotation"),
    ),
    "skeleton": StageContract(
        node_id="skeleton",
        title="Structure Draft",
        inputs=("seed", "context_meta", "title", "annotation"),
        outputs=("markdown", "intro_section", "blueprint"),
        prompt_id="generator.skeleton",
        model_role="planner",
        validators=("structural preflight", "ReadmeDocument"),
        repair_policy="repair fixable structural issues once",
        fallback_policy="deterministic README scaffold",
        observability_tags=("workflow", "generation", "llm", "structure"),
    ),
    "theory": StageContract(
        node_id="theory",
        title="Theory",
        inputs=("seed", "markdown", "practice_plan_contract", "section_contexts"),
        outputs=("markdown", "theory_parts", "warnings", "issues"),
        prompt_id="generator.theory",
        model_role="theory",
        validators=("TheoryPart", "TheoryValidator"),
        repair_policy="parse/repair theory parts and sanitize markdown",
        fallback_policy="keep skeleton section and emit hard issue",
        observability_tags=("workflow", "generation", "llm", "theory"),
    ),
    "practice": StageContract(
        node_id="practice",
        title="Practice",
        inputs=("seed", "markdown", "practice_plan_contract", "artifact_chain_plan"),
        outputs=("markdown", "practice_tasks", "dataset_files", "evidence_specs"),
        prompt_id="generator.practice",
        model_role="practice",
        validators=("PracticeTask", "PracticeValidator", "artifact chain"),
        repair_policy="critic-guided repair and artifact materialization",
        fallback_policy="preserve recoverable tasks and surface hard issues",
        observability_tags=("workflow", "generation", "llm", "practice"),
    ),
    "global_quality": StageContract(
        node_id="global_quality",
        title="Global Quality",
        kind="quality",
        inputs=("seed", "markdown"),
        outputs=("markdown",),
        prompt_id="generator.quality",
        model_role="critic",
        validators=("ReadmeDocument", "style", "toc"),
        repair_policy="coherence pass and markdown normalization",
        fallback_policy="return normalized input markdown",
        observability_tags=("workflow", "quality", "llm"),
    ),
    "evaluation": StageContract(
        node_id="evaluation",
        title="Final Evaluation",
        kind="scoring",
        inputs=("seed", "markdown"),
        outputs=("rubric_json", "issues"),
        prompt_id="checker.structural",
        model_role="critic",
        validators=("methodology skills", "MethodologyGate"),
        repair_policy="no mutation; route hard issues to gate",
        fallback_policy="deterministic validators remain authoritative",
        observability_tags=("workflow", "evaluation", "deterministic", "gate"),
    ),
    "translate": StageContract(
        node_id="translate",
        title="Translation",
        kind="quality",
        inputs=("seed", "markdown", "target_language"),
        outputs=("markdown", "translated_markdown"),
        prompt_id="translator.markdown",
        model_role="translator",
        validators=("protected blocks", "target language"),
        repair_policy="retry unsafe translated sections",
        fallback_policy="skip ru or keep original markdown",
        observability_tags=("workflow", "translation", "llm"),
    ),
    "finalize": StageContract(
        node_id="finalize",
        title="Finalize & Export",
        kind="finalize",
        inputs=("markdown", "rubric_json", "practice_tasks", "theory_parts"),
        outputs=("result", "assets", "project_spec", "generated_doc"),
        prompt_id="finalize.config",
        validators=("GeneratedDoc", "report payload"),
        repair_policy="assemble only",
        fallback_policy="fail when final document is absent",
        observability_tags=("workflow", "finalize", "deterministic"),
    ),
}

STANDARD_WORKFLOW_PROFILE = WorkflowProfile(
    id="standard",
    title="Обычный режим",
    stages=("context", "task_planning", "title_annotation", "skeleton", "theory", "practice", "global_quality", "evaluation", "finalize"),
)
METHODOLOGY_WORKFLOW_PROFILE = WorkflowProfile(
    id="methodology",
    title="Методологический режим",
    stages=STANDARD_WORKFLOW_PROFILE.stages,
    capabilities=WorkflowCapabilities(methodology_assistant=True, stage_review=True),
)
WORKFLOW_PROFILES = {
    STANDARD_WORKFLOW_PROFILE.id: STANDARD_WORKFLOW_PROFILE,
    METHODOLOGY_WORKFLOW_PROFILE.id: METHODOLOGY_WORKFLOW_PROFILE,
}


def stage_contract(node_id: str, *, fallback_name: str | None = None) -> StageContract:
    """Return a known stage contract or a deterministic fallback contract for custom stages."""
    key = node_id.strip()
    if key in GENERATOR_STAGE_CONTRACTS:
        return GENERATOR_STAGE_CONTRACTS[key]
    return StageContract(node_id=key, title=fallback_name or key, prompt_id=f"custom.{key}")


def resolve_workflow_profile(profile_id: str | WorkflowProfile | None) -> WorkflowProfile:
    """Return a workflow profile by id, defaulting to standard."""
    if isinstance(profile_id, WorkflowProfile):
        return profile_id
    return WORKFLOW_PROFILES.get(str(profile_id or "standard"), STANDARD_WORKFLOW_PROFILE)
