from __future__ import annotations

from app.core.methodology.rules import GeneratedDoc
from app.modules.checker.service import evaluate_content_sufficiency


def test_content_sufficiency_accepts_complete_theory_and_practice_metadata() -> None:
    result = evaluate_content_sufficiency(
        GeneratedDoc(
            markdown="# Project",
            metadata={
                "theory_parts": [_theory_part("REST"), _theory_part("OpenAPI"), _theory_part("Git")],
                "practice_tasks": [_practice_task(1), _practice_task(2)],
            },
        )
    )

    assert result.passed is True
    assert result.rubric_json["issues"] == []
    assert result.gate_review.human_review_required is False


def test_content_sufficiency_catches_missing_theory_and_practice_contracts() -> None:
    result = evaluate_content_sufficiency(
        GeneratedDoc(
            markdown="# Project",
            metadata={
                "theory_parts": [
                    {
                        "title": "REST",
                        "body": "REST помогает описывать взаимодействие.",
                        "word_count": 20,
                        "example": "",
                        "bridge_questions": [],
                        "definitions_found": [],
                        "covers_outcomes": [],
                    }
                ],
                "practice_tasks": [
                    {
                        "title": "Плохая задача",
                        "situation": "Коротко.",
                        "input_data": "нет",
                        "goal": "Изучить REST API.",
                        "approach_bullets": ["почитать"],
                        "expected_artifact": "Файл",
                        "artifact_location": "",
                        "p2p_criteria": ["Проверить качество."],
                        "covered_outcomes": [],
                        "theory_support": [],
                        "constraints_or_risk": "",
                    }
                ],
            },
        )
    )
    codes = {issue.code for issue in result.issues}

    assert result.passed is False
    assert result.rubric_json["hard_count"] >= 6
    assert result.gate_review.human_review_required is True
    assert "content_sufficiency.theory_parts_count" in codes
    assert "content_sufficiency.theory_part_length" in codes
    assert "content_sufficiency.theory_example_missing" in codes
    assert "content_sufficiency.theory_bridge_missing" in codes
    assert "content_sufficiency.practice_goal_passive" in codes
    assert "content_sufficiency.practice_p2p_missing" in codes


def _theory_part(title: str) -> dict[str, object]:
    return {
        "title": title,
        "body": f"**{title}** - это рабочее понятие проекта, которое связывает теорию и практику.",
        "word_count": 130,
        "example": f"Пример: участник применяет {title} в артефакте проекта.",
        "bridge_questions": [f"Как {title} влияет на итоговый артефакт?"],
        "definitions_found": [title],
        "covers_outcomes": ["Проектирует REST API"],
    }


def _practice_task(index: int) -> dict[str, object]:
    artifact = f"docs/task-{index:02d}/README.md"
    return {
        "title": f"Задание {index}",
        "situation": "Команда согласует контракт API, и ревьюеру нужно увидеть проверяемый артефакт.",
        "input_data": "Используй сырые заметки из `materials/context.md` и ограничения проекта.",
        "goal": "Спроектировать проверяемый артефакт REST API.",
        "approach_bullets": ["Опиши контракт API.", "Свяжи решение с OpenAPI и Git."],
        "expected_artifact": f"Документ размещён по пути `{artifact}`.",
        "artifact_location": artifact,
        "p2p_criteria": [
            f"Файл есть по указанному пути `{artifact}`.",
            "Документ содержит минимум два проверяемых раздела.",
            "В разделе указан источник входных данных.",
        ],
        "covered_outcomes": ["Проектирует REST API"],
        "theory_support": ["OpenAPI", "Git"],
        "constraints_or_risk": "Нельзя подменять сырые данные готовым решением.",
    }
