"""Generator runtime service backed by persisted curriculum plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.models import ArtifactRef, CurriculumContext, GeneratedDoc
from app.modules.curriculum.repo import CurriculumCatalogRepo
from app.modules.generator.engine import EngineStage, GeneratorEngineResult, GeneratorMethodologyEngine
from app.modules.generator.stages import head as head_stage
from app.modules.generator.stages import generators as generators_stage
from app.modules.generator.stages import practice as practice_stage
from app.modules.generator.stages import practice_review as practice_review_stage
from app.modules.generator.stages import theory as theory_stage

EngineFactory = Callable[..., GeneratorMethodologyEngine]


class CurriculumContextNotFound(ValueError):
    """Raised when a persisted curriculum project cannot be resolved."""


@dataclass(frozen=True, slots=True)
class GeneratorRun:
    """Generator execution result bound to the DB curriculum context used as input."""

    context: CurriculumContext
    document: GeneratedDoc
    engine_result: GeneratorEngineResult


class GeneratorService:
    """Generates project markdown from a persisted curriculum context."""

    def __init__(
        self,
        curriculum_repo: CurriculumCatalogRepo,
        *,
        engine_factory: EngineFactory = GeneratorMethodologyEngine,
    ) -> None:
        self.curriculum_repo = curriculum_repo
        self.engine_factory = engine_factory

    def generate_from_curriculum(
        self,
        *,
        plan_id: int,
        project_order: int,
        profile_id: str = "_base",
        program_type: str | None = None,
    ) -> GeneratorRun:
        context = self.curriculum_repo.get_context(plan_id, project_order)
        if context is None:
            raise CurriculumContextNotFound(f"curriculum project not found: plan_id={plan_id}, project_order={project_order}")

        engine = self.engine_factory(profile_id, program_type=program_type)
        template_blocks = _template_blocks(engine)
        result = engine.run(
            [
                EngineStage("curriculum.planner", lambda _ctx, _augment: {}),
                EngineStage(
                    "generator.head",
                    head_stage.run,
                    node_id="skeleton",
                    outputs=("title", "annotation", "intro_section", "task_plan", "context_analysis", "markdown", "head"),
                    gate_stage="skeleton",
                ),
                EngineStage(
                    "generator.theory",
                    theory_stage.run,
                    node_id="theory",
                    inputs=("curriculum_context", "markdown", "task_plan", "context_analysis"),
                    outputs=("markdown", "theory_parts", "theory", "theory_warnings", "theory_issues"),
                    gate_stage="theory",
                ),
                EngineStage(
                    "generator.practice",
                    practice_stage.run,
                    node_id="practice",
                    inputs=("curriculum_context", "markdown", "task_plan", "theory_parts", "artifact_chain_plan"),
                    outputs=("markdown", "practice_tasks", "artifact_chain_plan", "evidence_specs", "dataset_files"),
                    gate_stage="practice",
                ),
                EngineStage(
                    "generator.practice_review",
                    practice_review_stage.run,
                    node_id="practice",
                    inputs=("curriculum_context", "markdown", "practice_tasks", "theory_parts", "artifact_chain_plan"),
                    outputs=("markdown", "practice_tasks", "bonus_tasks", "practice_critic_issues", "practice_repaired_issue_count"),
                    gate_stage="practice",
                ),
                EngineStage(
                    "generator.generators",
                    generators_stage.run,
                    node_id="generators",
                    inputs=("curriculum_context", "markdown", "practice_tasks", "theory_parts", "evidence_specs", "artifact_chain_plan"),
                    outputs=("markdown", "generated_assets", "formula_assets", "dataset_files", "code_examples", "artifacts"),
                    gate_stage="practice",
                ),
                EngineStage(
                    "generator.finalize",
                    lambda ctx, _augment: _document_from_context(context, ctx, template_blocks),
                    node_id="finalize",
                    outputs=("generated_doc", "markdown"),
                ),
                EngineStage(
                    "generator.evaluation",
                    lambda ctx, _augment: ctx["generated_doc"],
                    node_id="evaluation",
                    inputs=("generated_doc", "markdown"),
                    gate_stage="evaluation",
                ),
            ],
            _engine_context(context),
        )
        document = result.documents["generator.evaluation"]
        return GeneratorRun(context=context, document=document, engine_result=result)


def _engine_context(context: CurriculumContext) -> dict[str, Any]:
    project = context.current_project_payload()
    return {
        "curriculum_context": context.model_dump(mode="json"),
        "curriculum.projects": [project],
        "current_project": project,
        "reference.competencies": [ref.model_dump(mode="json") for ref in context.current_project_competency_refs],
    }


def _template_blocks(engine: GeneratorMethodologyEngine) -> str:
    skill = engine.harness.profile.skills.get("template_blocks")
    if not skill:
        return ""
    return str(skill.params.get("blocks_markdown", "")).strip()


def _document_from_context(context: CurriculumContext, engine_context: dict[str, Any], template_blocks: str) -> GeneratedDoc:
    head_markdown = str(engine_context.get("markdown") or "").strip()
    has_practice = bool(engine_context.get("practice_tasks"))
    markdown = "\n\n".join(
        part
        for part in [
            head_markdown or f"# {context.current_project_title}",
            _project_context_markdown(context, nested=bool(head_markdown)),
            "" if has_practice else _task_markdown(context, engine_context, nested=bool(head_markdown)),
            _checklist_markdown(nested=bool(head_markdown)),
            template_blocks,
        ]
        if part.strip()
    )
    return GeneratedDoc(
        markdown=markdown,
        artifacts=_artifact_refs(engine_context.get("artifacts")),
        project_id=context.current_project_platform_name or context.current_project_title,
        metadata={
            "source": "curriculum_db",
            "plan_id": context.plan_id,
            "project_order": context.current_project_order,
            "artifact_target": "readme_project",
            "template_blocks_required": True,
            "curriculum_context": context.model_dump(mode="json"),
            "theory_parts": engine_context.get("theory_parts") or [],
            "practice_tasks": engine_context.get("practice_tasks") or [],
            "bonus_tasks": engine_context.get("bonus_tasks") or [],
            "practice_critic_issues": engine_context.get("practice_critic_issues") or [],
            "practice_repaired_issue_count": engine_context.get("practice_repaired_issue_count") or 0,
            "artifact_chain_plan": engine_context.get("artifact_chain_plan") or {},
            "evidence_specs": engine_context.get("evidence_specs") or [],
            "generated_assets": engine_context.get("generated_assets") or {},
            "formula_assets": engine_context.get("formula_assets") or {},
            "dataset_files": engine_context.get("dataset_files") or [],
            "code_examples": engine_context.get("code_examples") or [],
        },
    )


def _artifact_refs(raw: Any) -> list[ArtifactRef]:
    if not isinstance(raw, list):
        return []
    refs: list[ArtifactRef] = []
    for item in raw:
        try:
            refs.append(item if isinstance(item, ArtifactRef) else ArtifactRef.model_validate(item))
        except Exception:
            continue
    return refs


def _project_context_markdown(context: CurriculumContext, *, nested: bool = False) -> str:
    outcomes = context.current_project_learning_outcomes or ["Объяснить и применить ключевые действия проекта."]
    skills = context.current_project_skills or ["Практическая работа с задачей проекта."]
    tools = [*context.current_project_required_tools, *context.current_project_required_software]
    tool_line = ", ".join(tools) if tools else "инструменты не требуются"
    previous = ", ".join(project.title for project in context.previous_projects) or "это первый проект в блоке"
    next_items = ", ".join(project.title for project in context.next_projects) or "следующий проект не задан"
    heading = "### Контекст проекта" if nested else "## Контекст проекта"
    return "\n".join(
        [
            heading,
            f"- Блок: {context.block_name}.",
            f"- Цели блока: {', '.join(context.block_goals) or 'цели блока не заданы'}.",
            f"- Описание: {context.current_project_description or 'описание проекта не задано'}.",
            f"- Предыдущие проекты: {previous}.",
            f"- Следующие проекты: {next_items}.",
            f"- Инструменты: {tool_line}. Используй официальный источник; доступно в России; лицензия проверена; версия 1.0 или версия из учебного окружения.",
            "",
            "### Образовательные результаты",
            *[f"- {item}" for item in outcomes],
            "",
            "### Навыки",
            *[f"- {item}" for item in skills],
        ]
    )


def _task_markdown(context: CurriculumContext, engine_context: dict[str, Any], *, nested: bool = False) -> str:
    workload = engine_context.get("curriculum.workload_plan") or []
    task_plan = engine_context.get("task_plan") if isinstance(engine_context.get("task_plan"), dict) else {}
    workload_line = ""
    if workload:
        first = workload[0]
        workload_line = f" Ориентир: {first.get('workload_hours')} часов, {first.get('reviews_required')} p2p-проверки."
    elif task_plan:
        workload_line = f" План: {task_plan.get('tasks_count')} задач уровня {task_plan.get('complexity')}."
    story = context.sjm_context or "Работай с учебным кейсом и фиксируй решения в репозитории."
    materials = context.additional_materials or "используй материалы, указанные в учебном плане."
    heading = "### Практическое задание" if nested else "## Задание"
    return "\n".join(
        [
            heading,
            f"{story}{workload_line}",
            "",
            "1. Изучи контекст проекта и выдели ограничение, которое влияет на решение.",
            "2. Подготовь минимальную рабочую реализацию или артефакт по описанию проекта.",
            f"3. Сверь результат с материалами: {materials}",
            "4. Перед p2p-проверкой убедись, что результат запускается без ошибок.",
        ]
    )


def _checklist_markdown(*, nested: bool = False) -> str:
    heading = "### check-list.yml" if nested else "## check-list.yml"
    return f"""{heading}

```yaml
checks:
  - text: "README содержит минимум 3 раздела: контекст, задание и критерии проверки."
  - text: "Решение запускается без ошибок после выполнения инструкции."
  - text: "Итоговый артефакт содержит ссылку или файл с результатом работы."
```
"""
