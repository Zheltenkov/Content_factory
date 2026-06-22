"""Thin generator engine adapter for methodology harness and gate."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.core.llm.observe import LLMTraceRecorder, ObservedLLMClient, stable_input_hash
from app.core.methodology.gate import MethodologyGate, StageReviewResult
from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rubric import rule_issues_to_rubric
from app.core.methodology.rules import GeneratedDoc, RuleIssue
from app.modules.generator.domain import (
    StageContract,
    StageExecution,
    WorkflowProfile,
    WorkflowSnapshot,
    resolve_workflow_profile,
    stage_contract,
)

StageFn = Callable[[dict[str, Any], str], GeneratedDoc | dict[str, Any] | str | None]
StageCondition = Callable[[dict[str, Any]], bool]
PROFILES_ROOT = Path(__file__).resolve().parents[2] / "core" / "methodology" / "profiles"


@dataclass(frozen=True, slots=True)
class EngineStage:
    """One namespaced generator/curriculum/checker stage executable by the engine."""

    name: str
    run: StageFn
    node_id: str | None = None
    title: str | None = None
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    gate_stage: str | None = None
    run_if: StageCondition | None = None
    skip_if: StageCondition | None = None


@dataclass(slots=True)
class GeneratorEngineResult:
    """Execution result with methodology artifacts ready for trace/UI."""

    run_id: str
    context: dict[str, Any]
    documents: dict[str, GeneratedDoc] = field(default_factory=dict)
    prompt_augments: dict[str, str] = field(default_factory=dict)
    rule_issues: list[RuleIssue] = field(default_factory=list)
    rubric_json: dict[str, Any] = field(default_factory=dict)
    gate_review: StageReviewResult | None = None
    workflow: WorkflowSnapshot | None = None
    stage_results: list[StageExecution] = field(default_factory=list)
    stage_reviews: dict[str, StageReviewResult] = field(default_factory=dict)
    llm_traces: list[dict[str, Any]] = field(default_factory=list)


class GeneratorWorkflowError(RuntimeError):
    """Raised when a generator workflow stage fails unexpectedly."""


class GeneratorMethodologyEngine:
    """Run stages through harness hooks and finish with MethodologyGate evaluation."""

    def __init__(
        self,
        profile_id: str = "_base",
        *,
        program_type: str | None = None,
        profile_root: Path = PROFILES_ROOT,
        gate: MethodologyGate | None = None,
        run_id: str | None = None,
        user_id: str | None = None,
        workflow_profile: str | WorkflowProfile | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self.profile = resolve_profile(profile_id, profile_root, program_type=program_type)
        self.harness = Harness(self.profile)
        self.gate = gate or MethodologyGate()
        self.run_id = run_id
        self.user_id = user_id
        self.workflow_profile = resolve_workflow_profile(workflow_profile)
        self._raw_llm_client = llm_client
        self._llm_trace_recorder = LLMTraceRecorder()

    def run(self, stages: Iterable[EngineStage], context: dict[str, Any] | None = None) -> GeneratorEngineResult:
        stage_list = list(stages)
        ctx = dict(context or {})
        run_id = str(ctx.get("run_id") or self.run_id or uuid.uuid4())
        ctx["run_id"] = run_id
        ctx["workflow_profile"] = self.workflow_profile.model_dump(mode="json")
        ctx["llm_traces"] = self._llm_trace_recorder.events
        workflow = WorkflowSnapshot(
            run_id=run_id,
            user_id=self.user_id,
            metadata={"workflow_profile": self.workflow_profile.id},
        )
        workflow.start(len(stage_list))
        documents: dict[str, GeneratedDoc] = {}
        augments: dict[str, str] = {}
        issues: list[RuleIssue] = []
        stage_results: list[StageExecution] = []
        stage_reviews: dict[str, StageReviewResult] = {}

        for index, stage in enumerate(stage_list, 1):
            contract = _contract_for_stage(stage)
            workflow.node_started(contract.node_id, index)
            if _should_skip(stage, ctx):
                execution = _stage_execution(
                    run_id=run_id,
                    stage=stage,
                    contract=contract,
                    checkpoint_index=index,
                    status="skipped",
                    started=time.perf_counter(),
                    input_payload=_stage_input(ctx, contract),
                    output_keys=[],
                    output_artifact={},
                    issues=["condition=false"],
                    review=None,
                )
                workflow.node_completed(execution)
                stage_results.append(execution)
                continue

            started = time.perf_counter()
            before_keys = set(ctx)
            input_payload = _stage_input(ctx, contract)
            try:
                ctx = self.harness.prepare(stage.name, ctx)
                augment = self.harness.augment(stage.name, ctx)
                if augment:
                    augments[stage.name] = augment
                if self._raw_llm_client is not None:
                    ctx["llm_client"] = ObservedLLMClient(
                        self._raw_llm_client,
                        self._llm_trace_recorder,
                        run_id=run_id,
                        stage=stage.name,
                        metadata=contract.trace_metadata(),
                    )
                output = stage.run(ctx, augment)
                ctx, doc = _merge_output(ctx, output)
                stage_issue_messages: list[str] = []
                if doc is not None:
                    documents[stage.name] = doc
                    new_issues = self.harness.validate(stage.name, doc, ctx)
                    issues.extend(new_issues)
                    stage_issue_messages.extend(_rule_issue_message(issue) for issue in new_issues)
                rubric = rule_issues_to_rubric(issues)
                ctx["rubric_json"] = rubric
                review = self.gate.review(stage.gate_stage, ctx) if stage.gate_stage else None
                if review is not None:
                    stage_reviews[stage.name] = review
                    stage_issue_messages.extend(review.flow_issue_messages())
                output_keys = _output_keys(before_keys, ctx, contract)
                execution = _stage_execution(
                    run_id=run_id,
                    stage=stage,
                    contract=contract,
                    checkpoint_index=index,
                    status="success",
                    started=started,
                    input_payload=input_payload,
                    output_keys=output_keys,
                    output_artifact=_compact_artifact({key: ctx.get(key) for key in output_keys}),
                    issues=stage_issue_messages,
                    review=review,
                )
                workflow.node_completed(execution)
                stage_results.append(execution)
            except Exception as exc:  # noqa: BLE001 - workflow boundary must attach a checkpoint
                execution = _stage_execution(
                    run_id=run_id,
                    stage=stage,
                    contract=contract,
                    checkpoint_index=index,
                    status="error",
                    started=started,
                    input_payload=input_payload,
                    output_keys=[],
                    output_artifact={},
                    issues=[str(exc)],
                    review=None,
                )
                workflow.node_completed(execution)
                workflow.fail(str(exc))
                stage_results.append(execution)
                ctx["workflow"] = workflow.model_dump(mode="json")
                ctx["stage_results"] = [item.model_dump(mode="json") for item in stage_results]
                raise GeneratorWorkflowError(f"Generator stage '{stage.name}' failed: {exc}") from exc

        rubric = rule_issues_to_rubric(issues)
        ctx["rubric_json"] = rubric
        ctx["llm_traces"] = self._llm_trace_recorder.events
        review = self.gate.review("evaluation", ctx)
        needs_review = review.human_review_required or any(item.human_review_required for item in stage_reviews.values())
        workflow.complete(needs_review=needs_review)
        ctx["workflow"] = workflow.model_dump(mode="json")
        ctx["stage_results"] = [item.model_dump(mode="json") for item in stage_results]
        ctx["stage_reviews"] = {key: value.model_dump(mode="json") for key, value in stage_reviews.items()}
        return GeneratorEngineResult(
            run_id=run_id,
            context=ctx,
            documents=documents,
            prompt_augments=augments,
            rule_issues=issues,
            rubric_json=rubric,
            gate_review=review,
            workflow=workflow,
            stage_results=stage_results,
            stage_reviews=stage_reviews,
            llm_traces=list(self._llm_trace_recorder.events),
        )


def _merge_output(ctx: dict[str, Any], output: GeneratedDoc | dict[str, Any] | str | None) -> tuple[dict[str, Any], GeneratedDoc | None]:
    if output is None:
        return ctx, None
    if isinstance(output, GeneratedDoc):
        return _attach_doc(ctx, output), output
    if isinstance(output, str):
        doc = GeneratedDoc(markdown=output)
        return _attach_doc(ctx, doc), doc
    if isinstance(output, dict):
        next_ctx = {**ctx, **output}
        raw_doc = output.get("generated_doc")
        if isinstance(raw_doc, GeneratedDoc):
            return _attach_doc(next_ctx, raw_doc), raw_doc
        markdown = output.get("markdown")
        if isinstance(markdown, str):
            doc = GeneratedDoc(
                markdown=markdown,
                images=list(output.get("images") or []),
                artifacts=list(output.get("artifacts") or []),
                project_id=output.get("project_id"),
                metadata=dict(output.get("metadata") or {}),
            )
            return _attach_doc(next_ctx, doc), doc
        return next_ctx, None
    raise TypeError(f"Unsupported stage output: {type(output)!r}")


def _attach_doc(ctx: dict[str, Any], doc: GeneratedDoc) -> dict[str, Any]:
    return {**ctx, "generated_doc": doc, "markdown": doc.markdown}


def _contract_for_stage(stage: EngineStage) -> StageContract:
    node_id = stage.node_id or _node_id_from_stage_name(stage.name)
    base = stage_contract(node_id, fallback_name=stage.title or stage.name)
    updates: dict[str, Any] = {}
    if stage.title:
        updates["title"] = stage.title
    if stage.inputs:
        updates["inputs"] = stage.inputs
    if stage.outputs:
        updates["outputs"] = stage.outputs
    return base.model_copy(update=updates) if updates else base


def _node_id_from_stage_name(name: str) -> str:
    raw = name.rsplit(".", 1)[-1]
    return "task_planning" if raw == "planner" else raw


def _should_skip(stage: EngineStage, ctx: dict[str, Any]) -> bool:
    if stage.run_if is not None and not stage.run_if(ctx):
        return True
    return bool(stage.skip_if is not None and stage.skip_if(ctx))


def _stage_input(ctx: dict[str, Any], contract: StageContract) -> dict[str, Any]:
    if contract.inputs:
        return {key: ctx.get(key) for key in contract.inputs if key in ctx and key != "llm_client"}
    return {"context_keys": sorted(str(key) for key in ctx if key != "llm_client")}


def _output_keys(before_keys: set[str], ctx: dict[str, Any], contract: StageContract) -> list[str]:
    declared = [key for key in contract.outputs if key in ctx]
    changed = sorted(key for key in set(ctx) - before_keys if key != "llm_client")
    keys = declared or changed
    return list(dict.fromkeys([*keys, *changed]))


def _stage_execution(
    *,
    run_id: str,
    stage: EngineStage,
    contract: StageContract,
    checkpoint_index: int,
    status: str,
    started: float,
    input_payload: dict[str, Any],
    output_keys: list[str],
    output_artifact: dict[str, Any],
    issues: list[str],
    review: StageReviewResult | None,
) -> StageExecution:
    return StageExecution(
        run_id=run_id,
        node_id=contract.node_id,
        stage_name=stage.name,
        checkpoint_index=checkpoint_index,
        status=status,  # type: ignore[arg-type]
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
        input_hash=stable_input_hash(input_payload),
        output_keys=output_keys,
        output_artifact=output_artifact,
        issues=issues,
        review_status=review.status if review is not None else None,
        human_review_required=bool(review and review.human_review_required),
    )


def _rule_issue_message(issue: RuleIssue) -> str:
    return f"skill:{issue.severity}:{issue.code}: {issue.message}"


def _compact_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _compact_value(value) for key, value in payload.items()}


def _compact_value(value: Any) -> Any:
    if isinstance(value, GeneratedDoc):
        return {
            "type": "GeneratedDoc",
            "markdown_chars": len(value.markdown),
            "project_id": value.project_id,
            "metadata_keys": sorted(value.metadata)[:20],
        }
    if isinstance(value, BaseModel):
        return _compact_value(value.model_dump(mode="json"))
    if isinstance(value, str):
        return {"type": "str", "chars": len(value), "preview": value[:500]}
    if isinstance(value, dict):
        items = list(value.items())[:20]
        compact = {str(key): _compact_value(item) for key, item in items}
        if len(value) > len(items):
            compact["_truncated_keys"] = len(value) - len(items)
        return compact
    if isinstance(value, list):
        items = [_compact_value(item) for item in value[:10]]
        if len(value) > len(items):
            items.append({"_truncated_items": len(value) - len(items)})
        return items
    if isinstance(value, tuple | set):
        return _compact_value(list(value))
    return value
