from __future__ import annotations

from app.modules.checker.structural import evaluate_readme


CLEAN_README = """# Backend Project

Аннотация описывает учебный проект, его цель, ожидаемый результат и связь с практикой. Текст идет сразу после H1 и остается связным абзацем без списков.

## Содержание

- [Глава 1](#глава-1-введение)
- [Глава 2](#глава-2-теория)
- [Глава 3](#глава-3-практика)

## Глава 1. Введение

Проект знакомит участника с устройством сервиса, границами задачи и ожидаемыми артефактами. Здесь фиксируется контекст и критерии результата.

## Глава 2. Теория

Раздел объясняет архитектурные понятия, контракты API, хранение данных и наблюдаемость. Материал связывает решения с практическим заданием.

## Глава 3. Практика

Участник реализует сервис, пишет тесты, проверяет контракт и готовит итоговый репозиторий. Задание описано проверяемыми шагами.

| Поле | Назначение |
| --- | --- |
| API | Контракт взаимодействия |
"""


BROKEN_README = """Без H1

## Содержание
- мало

## Глава 1. Введение
Коротко.

| Поле | Назначение |
| --- | --- |
| API |

TODO: заполнить практику.

```python
print("unclosed")
"""


def test_structural_axis_passes_clean_readme() -> None:
    result = evaluate_readme(CLEAN_README)

    assert result.passed is True
    assert result.rubric_json["passed"] is True
    assert result.rubric_json["issues"] == []
    assert {"readme_structure", "document_integrity"}.issubset(result.active_skills)
    assert result.gate_review.human_review_required is False


def test_structural_axis_catches_broken_readme_and_returns_gate_rubric() -> None:
    result = evaluate_readme(BROKEN_README)
    codes = {issue.code for issue in result.issues}

    assert result.passed is False
    assert result.rubric_json["passed"] is False
    assert result.rubric_json["hard_count"] >= 4
    assert result.gate_review.human_review_required is True
    assert "readme_structure.h1_first" in codes
    assert "readme_structure.annotation_missing" in codes
    assert "readme_structure.toc_missing" in codes
    assert "document_integrity.table_columns" in codes
    assert "document_integrity.placeholder" in codes
    assert "document_integrity.unclosed_fence" in codes
