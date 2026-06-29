# TASKS.md — архив переносного бэклога

Этот файл больше не является активным ТЗ. Атомарные задачи волн 0–7 использовались как рабочий
чеклист консолидации `Spravochnik` + `Content_generator_ver1` + `Proverka` в единый монорепозиторий
`Content_factory`.

## Статус

- Каркас, core, methodology skills/profiles, curriculum/catalog, generator, translator, checker,
  reference/UI, reverse-extraction, revision loop и CI-гейты перенесены в `app/`, `migrations/`,
  `scripts/ci/` и `tests/`.
- Alembic-цепочка поднята до `015`.
- Локальный PG DoD выполнен: `alembic current -> 015 (head)`.
- GitNexus-индекс текущего монорепо создан и актуален на `main`.

## Где теперь проверять состояние

- Архитектура и целевая структура: `docs/CONSOLIDATION_PLAN.md`.
- Принятые решения: `docs/DECISIONS.md`.
- Контракты разработки и CI-гейты: `AGENTS.md`.
- Автоматическая приёмка: `pytest`, `scripts/ci/check_line_budget.py`,
  `scripts/ci/check_grep_gates.py`, `scripts/ci/check_duplicates.py`.

## Финальные операционные хвосты

- Провести live-приёмку в браузере на реальной локальной PG.
- После подтверждения parity пометить legacy-репозитории как archived/read-only.
