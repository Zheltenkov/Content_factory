"""HTTP API for generator runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.methodology.gate.models import StageReviewResult
from app.core.models import CurriculumContext, GeneratedDoc, RuleIssue
from app.modules.curriculum.repo import CurriculumCatalogRepo, default_curriculum_repo
from app.modules.generator.service import CurriculumContextNotFound, GeneratorService

router = APIRouter(prefix="/generator", tags=["generator"])


class GenerateFromCurriculumRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: int = Field(ge=1)
    project_order: int = Field(ge=1)
    profile_id: str = "_base"
    program_type: str | None = None


class GeneratorRunResponse(BaseModel):
    context: CurriculumContext
    document: GeneratedDoc
    rule_issues: list[RuleIssue]
    rubric_json: dict[str, object]
    gate_review: StageReviewResult | None


def get_generator_repo() -> CurriculumCatalogRepo:
    return default_curriculum_repo()


@router.post("/runs/from-curriculum", response_model=GeneratorRunResponse)
def generate_from_curriculum(
    payload: GenerateFromCurriculumRequest,
    repo: CurriculumCatalogRepo = Depends(get_generator_repo),
) -> GeneratorRunResponse:
    service = GeneratorService(repo)
    try:
        run = service.generate_from_curriculum(
            plan_id=payload.plan_id,
            project_order=payload.project_order,
            profile_id=payload.profile_id,
            program_type=payload.program_type,
        )
    except CurriculumContextNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return GeneratorRunResponse(
        context=run.context,
        document=run.document,
        rule_issues=run.engine_result.rule_issues,
        rubric_json=run.engine_result.rubric_json,
        gate_review=run.engine_result.gate_review,
    )
