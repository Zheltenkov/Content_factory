# document_integrity — третий эталонный скилл

Кросс-документная целостность (N.1–N.5 из `structural_criteria_v2`), вынесенная из `readme_structure`
в отдельный скилл по v2-структуре. Тесты зелёные (`5/5`).

## Что этот образец демонстрирует (чего не было в первых двух)
1. **Чисто машинный скилл — без `instructions.md`.** Только `post.validate` + `check.py`. Допустимый
   случай «только правило» (§3 спека): скилл ничего не вклеивает в промпт, лишь проверяет результат.
2. **Cross-artifact.** Не зависит от каркаса — работает на сырой структуре markdown (таблицы, fenced,
   кавычки, диаграммы, project-id). `applies_to.artifact_family: [readme, lesson, guide]`. Тест гоняет
   его и на README-, и на lesson-документе.
3. **Namespaced-хуки v2:** `post.validate` на `generator.evaluation` И `checker.evaluation`.

## Дерево (канонический путь v2)
```
core/methodology/rules.py                                  # контракт (общий)
core/methodology/profiles/_base/skills/document_integrity/
├── skill.yaml                                             # validator-only, applies_to, params
└── check.py                                               # N.1-N.5, детерминированно, ~170 строк
tests/test_document_integrity.py                           # clean README + clean lesson + битый
```
> `readme_structure` и `visual_quality` из прошлой поставки переезжают в тот же родитель
> `core/methodology/profiles/_base/skills/`.

## Запуск
```bash
PYTHONPATH=. python3 tests/test_document_integrity.py     # или pytest
```

## Пять проверок
| N | Что ловит | Severity |
|---|---|---|
| **N.1** tables | рваная таблица: число колонок строки ≠ шапке, разделитель ≠ шапке, пустая таблица | hard |
| **N.2** template bleed | шаблонные плейсхолдеры (TODO/ЗАПОЛНИ/<...>); дословно повторяющиеся блоки; доля повторов > порога | hard |
| **N.3** diagram↔topic | диаграмма без ближайшего заголовка/подписи (hard); нулевое пересечение слов диаграммы с темой (soft, эвристика) | hard / soft |
| **N.4** broken text | незакрытый ``` (hard); несбалансированные «…» (soft); оборванное предложение перед заголовком (soft) | hard / soft |
| **N.5** project-id | чужой id при заданном `doc.project_id` (hard); несколько разных id (hard) | hard |

## Заложенные ограничения (честно)
- **N.3 — эвристика, не семантика.** «Нет заголовка» жёстко; «слова не пересекаются» — мягко (ложит
  при синонимах/инфлексии). Семантическую сверку — отдельным шагом позже, не на старте.
- **N.5 — узкий паттерн слага** (`префикс+цифра_CamelCase`), чтобы не ловить `ENV_VARS`/`CONSTANTS`.
  Конкретный проект переопределяет `project_id_pattern` под свою схему именования.
- **N.2 — повтор по нормализованному хэшу блока** (точные дубли). Near-duplicate (перефраз) — это уже
  дидактическая ось (жюри), не структурная.
