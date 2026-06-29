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


def test_structural_axis_catches_document_integrity_n1_to_n5() -> None:
    repeated = (
        "Повторяемый шаблонный блок описывает одну и ту же активность без новых требований, "
        "артефактов, критериев и контекста для студента. "
    )
    broken = f"""# DO4_LinuxMonitoring

Аннотация достаточной длины описывает учебный проект, но ниже специально оставлены дефекты целостности документа.

## Содержание

- [Глава 1](#глава-1-введение)
- [Глава 2](#глава-2-теория)
- [Глава 3](#глава-3-практика)

## Глава 1. Введение

Ссылка на чужой проект XX1_OtherProject должна быть поймана как foreign id.

| Поле | Назначение |
| --- | --- |
| API |

{repeated}

{repeated}

TODO: заменить шаблон.

## Глава 2. Теория

```mermaid
graph TD
  Database --> Cache
```

## Глава 3. Практика

```python
print("broken")
"""

    result = evaluate_readme(broken, project_id="DO4_LinuxMonitoring")
    codes = {issue.code for issue in result.issues}

    assert "document_integrity.table_columns" in codes
    assert "document_integrity.placeholder" in codes
    assert "document_integrity.repeated_block" in codes
    assert "document_integrity.diagram_topic_mismatch" in codes
    assert "document_integrity.unclosed_fence" in codes
    assert "document_integrity.foreign_project_id" in codes
