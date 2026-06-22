from __future__ import annotations

import re

from app.core.config import get_thresholds
from app.core.models import CurriculumContext, ProjectSummary
from app.modules.generator.stages.head import generate_head
from app.modules.generator.stages.theory import TheoryDraft, TheoryDraftPart, generate_theory


def test_theory_stage_generates_parts_definitions_and_replaces_chapter() -> None:
    context = _context()
    head = generate_head(context)
    result = generate_theory(context, markdown=head.markdown)
    parts_lo, parts_hi = get_thresholds().require_range("structural.theory_parts")
    words_lo, words_hi = get_thresholds().require_range("structural.theory_words_per_part")

    assert parts_lo <= len(result.parts) <= parts_hi
    assert result.markdown.startswith("# REST API")
    assert "## Глава 2. Теория" in result.markdown
    assert "### 2.1." in result.markdown
    assert "## Глава 3. Практика" in result.markdown
    assert result.markdown.index("## Глава 2. Теория") < result.markdown.index("## Глава 3. Практика")
    assert all(words_lo <= part.word_count <= words_hi for part in result.parts)
    assert all(part.definitions_found for part in result.parts)
    assert all(part.bridge_questions for part in result.parts)
    assert any("OpenAPI" in part.body or "openapi" in part.body.lower() for part in result.parts)


def test_theory_stage_sanitizes_short_no_code_draft_and_static_leaks() -> None:
    context = _context(direction="PJM", title="Документы заказчика")
    head = generate_head(context)
    draft = TheoryDraft(
        parts=[
            TheoryDraftPart(
                title="Псевдокод процесса",
                body=(
                    "P2P и чек-лист сдачи важны. Процесс — это порядок действий. "
                    "```python\nprint('bad')\n``` $$P = Q/T$$"
                ),
                example="```js\nconsole.log('bad')\n```",
                bridge_questions=["Что такое процесс?"],
            )
        ]
    )

    result = generate_theory(context, markdown=head.markdown, draft=draft)
    chapter = result.markdown.split("## Глава 2. Теория", 1)[1].split("## Глава 3. Практика", 1)[0]
    words_lo, _ = get_thresholds().require_range("structural.theory_words_per_part")

    assert len(result.parts) >= 3
    assert all(part.word_count >= words_lo for part in result.parts)
    assert not re.search(r"\b(P2P|чек-?лист)|```|\$\$", chapter, flags=re.I)
    assert not re.search(r"\bкод[а-я]*\b|псевдокод", chapter, flags=re.I)
    assert all(part.content_type == "no_code" for part in result.parts)
    assert all(not question.lower().startswith("что такое") for part in result.parts for question in part.bridge_questions)


def _context(*, direction: str = "Backend", title: str = "REST API") -> CurriculumContext:
    return CurriculumContext(
        plan_id=1,
        plan_title="Backend curriculum",
        direction=direction,
        block_name="API",
        block_goals=["Собрать сервис с понятным API"],
        current_project_order=2,
        current_project_title=title,
        current_project_description="Команда проектирует сервис и оформляет контракт взаимодействия.",
        current_project_learning_outcomes=["Проектирует REST API", "Описывает OpenAPI-контракт"],
        current_project_skills=["REST API", "OpenAPI", "Git"],
        current_project_audience_level="beginner",
        current_project_required_tools=["Git"],
        current_project_required_software=["OpenAPI"],
        current_project_workload_hours=8,
        previous_projects=[ProjectSummary(order=1, title="HTTP intro", learning_outcomes=["Понимает HTTP"])],
        next_projects=[ProjectSummary(order=3, title="Docker deploy", learning_outcomes=["Разворачивает сервис"])],
        sjm_context="Ты работаешь в команде сервиса и согласуешь контракт API с соседней командой.",
        additional_materials="materials/context.md",
    )
