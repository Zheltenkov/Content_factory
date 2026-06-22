from __future__ import annotations

from app.modules.checker.didactic.jury import collect_signals as collect_jury_signals
from app.modules.checker.signals import (
    collect_signals,
    diagram_signals,
    moss_similarity,
    near_duplicate_pairs,
    repetition_ratio,
    table_signals,
    text_similarity,
)


def test_similarity_detectors_rank_related_text_above_unrelated() -> None:
    related = text_similarity(
        "Проектирование REST API и настройка PostgreSQL для backend-сервиса.",
        "Разработка backend REST API с PostgreSQL и OpenAPI-контрактом.",
    )
    unrelated = text_similarity(
        "Проектирование REST API и настройка PostgreSQL для backend-сервиса.",
        "Композиция кадра, свет и цветокоррекция в видеомонтаже.",
    )

    assert related.score > unrelated.score
    assert moss_similarity("alpha beta gamma delta epsilon", "alpha beta gamma delta epsilon").score == 1.0
    assert text_similarity("", "").score == 0.0


def test_repetition_detectors_return_clean_and_broken_signals() -> None:
    clean = "Первый раздел объясняет контекст. Второй раздел показывает пример. Третий раздел связывает выводы."
    repeated = (
        "Настройка API начинается с контракта OpenAPI и проверки ошибок. "
        "Настройка API начинается с контракта OpenAPI и проверки ошибок. "
        "Далее студент добавляет логирование и тесты."
    )

    assert repetition_ratio(clean) == 0.0
    assert repetition_ratio(repeated) > 0.0
    assert near_duplicate_pairs(clean) == []
    assert near_duplicate_pairs(repeated)


def test_table_detector_returns_no_issue_for_clean_table_and_signal_for_broken_table() -> None:
    clean = """
| Поле | Описание |
| --- | --- |
| API | Контракт сервиса |
"""
    broken = """
| Поле | Описание |
| --- |
| API | Контракт сервиса | Дополнение |
"""

    assert table_signals(clean) == []
    issues = table_signals(broken)
    assert {item.code for item in issues} >= {"table_separator", "table_columns"}


def test_diagram_detector_scores_contextual_and_orphan_diagrams() -> None:
    contextual = """
## Проектирование API

```mermaid
graph TD
    API --> Contract
```
"""
    orphan = """
```mermaid
graph TD
    Queue --> Worker
```
"""

    contextual_signal = diagram_signals(contextual)[0]
    orphan_signal = diagram_signals(orphan)[0]

    assert contextual_signal.has_context is True
    assert contextual_signal.score > 0
    assert orphan_signal.has_context is False
    assert orphan_signal.score == 0


def test_collect_signals_unifies_checker_payload_for_axes() -> None:
    markdown = """
# Backend API
Аннотация объясняет маршрут проекта и ожидаемый результат.

## Содержание
- Глава 1
- Глава 2
- Глава 3

## Глава 1. Введение
**Пример 1.** Разбор входных данных.

| Поле | Описание |
| --- |
| API | Контракт сервиса | Дополнение |

Сделай шаг и скопируй решение. Сделай шаг и скопируй решение.

```mermaid
graph TD
    Queue --> Worker
```
"""

    signals = collect_signals(markdown)
    jury_payload = collect_jury_signals(markdown)

    assert signals.broken_tables >= 1
    assert signals.directive_hits >= 1
    assert signals.example_count >= 1
    assert signals.shape.has_h1 is True
    assert signals.shape.toc_lines >= 3
    assert jury_payload["broken_tables"] == signals.broken_tables
    assert jury_payload["diagram_match_avg"] == signals.diagram_match_avg
