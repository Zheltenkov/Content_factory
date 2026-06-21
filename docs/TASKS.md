# TASKS.md — атомарный бэклог консолидации (для Codex)

> Спутник `CONSOLIDATION_PLAN.md` (волны + DoD), `SKILLS_ARCHITECTURE.md` (слой правил),
> `AGENTS.md` (working agreement). Здесь — задачи по одной, в порядке зависимостей.
>
> **Правило исполнения:** одна сессия = одна задача = один модуль. Не брать следующую, пока тест
> текущей не зелёный и бюджет не соблюдён. Перед написанием — прочитать «Образец» и сделать `grep`,
> нет ли уже того, что собираешься писать. Подробности — в `AGENTS.md`.

**Легенда строки задачи:** `Файлы (бюджет строк)` · `Образец` (что копировать/смотреть) · `DoD` (проверяемый критерий, всегда включает зелёный тест).

**Готовые артефакты** (не переспецифицировать — переносить как есть): `harness_ref/` (harness + контракт + 3 профиля, тесты 5/5), три эталонных скилла (`readme_structure`, `visual_quality`, `document_integrity`, тесты зелёные). При переносе скиллов применить `on:`→`at:` (см. AGENTS §Контракты).

**Порядок волн:** 0 → 1 ∥ M → 2 → (3,4) → 5 → 6 → 7. Волна M (methodology) идёт параллельно/сразу после 1 — её эталоны готовы.

---

## Волна 0 — Каркас

- **T0.1 Монорепо-скелет.** `app/{core,modules,static}`, `migrations/`, `tests/`, `pyproject.toml`. Файлы: скелет (≤300). Образец: целевая структура `CONSOLIDATION_PLAN §2`. DoD: FastAPI-приложение поднимается, `/` отдаёт пустую дашборд-оболочку; `pytest` проходит (1 smoke-тест).
- **T0.2 ModuleManifest + MODULE_REGISTRY.** `core/registry.py`: dataclass (id, title, icon, router, ui_panel, tables, dashboard_tile) + автосборка плиток. Файлы: ≤200. Образец: `CONSOLIDATION_PLAN §2` (контракт модуля). DoD: дашборд рендерит плитки из реестра для пустых модулей; тест: регистрация модуля → плитка в выдаче `/api/modules`.
- **T0.3 alembic-базис.** Перенести 9 миграций CG, поднять PG. Файлы: `migrations/`. Образец: текущий `Content_generator/migrations`. DoD: `alembic upgrade head` чисто на пустом PG; тест коннекта.
- **T0.4 Схема Справочника → та же alembic-цепочка.** SQLite-DDL Spravochnik как PG-миграция (provenance, alias-нормализация, ai_analysis_*, review_queue). Файлы: 1 миграция. Образец: `Spravochnik/scripts/build_catalog_db.py`, `sql/`. DoD: таблицы каталога создаются в PG; тест на наличие ключевых таблиц.

## Волна 1 — core/ (ядро; зависит от 0)

- **T1.1 Перенести harness + контракт.** Скопировать `harness_ref/core/methodology/{rules.py,harness.py}` в репо. Файлы: как есть (~215). Образец: `harness_ref/` (готов). DoD: `tests/test_harness.py` 5/5 зелёный в репо.
- **T1.2 core/llm/.** Один клиент (из `content_gen/llm/`) + `structured.complete_typed(prompt, schema)->BaseModel` (repair-retry) + `observe` + загрузчик `prompts/<area>/<name>@v1.md`. Файлы: `core/llm/*` (≤1500). Образец: нет (перенос+слияние). DoD: `complete_typed` возвращает типизированный объект на mock-LLM; observe пишет run_id/stage/model/tokens; тест.
- **T1.3 core/models/.** Слить модель навыка CG + Spravochnik в ОДНУ; добавить `ProfilePackage`, `UPSkeleton`, `MethodologyContext`, `ArtifactRef`. Файлы: `core/models/*` (≤1500). Образец: `content_gen/models/`, Spravochnik skill-модели. DoD: импортируется без циклов; тесты сериализации; нет двух моделей навыка.
- **T1.4 core/methodology/gate.** Перенести MethodologyGate (3619 → ≤2500; чистка дублей trace). Файлы: `core/methodology/gate/*`. Образец: `content_gen/methodology/`. DoD: gate-тесты зелёные; `_review_evaluation` агрегирует `rubric_json`; на critical поднимает `human_review_required`.
- **T1.5 core/config/.** `settings.py` + `thresholds.yaml` — единый источник порогов (из `structural_criteria_v2`). Файлы: ≤400. Образец: `content_gen/config/`. DoD: пороги читаются скиллами из конфига; grep: нет числовых порогов хардкодом в `check.py`.

## Волна M — methodology/skills (зависит от T1.1; ∥ остальной волне 1)

- **TM.1 Положить 3 эталонных скилла.** В `core/methodology/profiles/_base/skills/{readme_structure,visual_quality,document_integrity}`, применив `on:`→`at:`. Образец: их zip'ы (готовы). DoD: их тесты зелёные; harness резолвит `_base` и грузит их check.py.
- **TM.2 Сгенерить остальные базовые скиллы из §8.1.** Один скилл = одна задача = одна сессия, строго по строке таблицы §8.1 и рецепту §11 спека. Образец: три эталона (augment→`voice`-стиль; validate→`visual_quality`/`document_integrity`; producer→`competency_weights` из `harness_ref`). Бюджет: `check.py` ≤150 каждый. DoD на скилл: `skill.yaml` (at:, namespaced-стадии, severity, params из §8) + `instructions.md` (если есть augment-хук) + `check.py` (если есть машинное правило) + тест (clean + битый).

  | # | Скилл | Тип | check.py |
  |---|---|---|---|
  | TM.2.1 | `voice` | augment | опц. (детект канцелярита) |
  | TM.2.2 | `content_sufficiency` | augment | нет (кормит дидактику) |
  | TM.2.3 | `branch_structure` | producer (planner) | prepare: порядок |
  | TM.2.4 | `audience_level` | producer (planner) | prepare |
  | TM.2.5 | `competency_weights` | producer (planner) | **готов в harness_ref** — перенести |
  | TM.2.6 | `software_constraints` | augment + validate | да |
  | TM.2.7 | `checklist` | augment + validate | да (yml, объективность) |
  | TM.2.8 | `repository_structure` | validate | да (директории, for_forks) |
  | TM.2.9 | `autotests` | producer (planner) | prepare (политика) |
  | TM.2.10 | `template_blocks` | augment + validate | да (присутствие/неизменность) |
  | TM.2.11 | `workload_planning` | producer (planner) | prepare (Y=X·0.34+3) |
  | TM.2.12 | `access_constructors` | producer (planner) | prepare |

- **TM.3 Профили kids + commerce.** `kids/` (overrides voice/checklist; disables readme_structure; adds program_types/lesson_structure/mentor_assets/assessments/student_portrait; program_types main/intensive/master_class) + `commerce/` (param-only: readme_cyclic). Образец: `harness_ref/profiles/{kids,commerce}` (готовы как каркас) + §8.2/8.3. DoD: harness резолвит kids (все 3 program_type) и commerce; инвариант `producers_bound_to("generator.")==[]`.
- **TM.4 Подключить harness к engine + gate.** Движок зовёт `augment/prepare/validate` на namespaced-стадиях; issues → gate как `rubric_json`. Файлы: интеграционный слой (≤300). Образец: `harness_ref` API + `CONSOLIDATION_PLAN §4`. DoD: e2e — генерация с активным профилем прогоняет skills; HARD-issue поднимает `human_review_required`.

## Волна 2 — curriculum/ + УП (зависит от 1; закрывает пробел №1 — персистентный УП)

- **T2.1 Перенос пайплайна каталога.** `stage_*` Spravochnik → `modules/curriculum/stages/`: модели из core, LLM через `structured`, конфиг из settings. Образец: `Spravochnik/spravochnik_intake/pipeline/`. DoD: `test_regression_pipeline` зелёный на PG.
- **T2.2 Планировщик.** `curriculum/planner/` — спиральный (перенос без изменения логики: Брунер/Харден/Хэтти). Образец: `Spravochnik/.../curriculum/planner.py`. DoD: планировщик-тесты зелёные.
- **T2.3 repo-слой.** Слить `competency_catalog`+`storage` в `curriculum/repo.py`; SQLite→PG. Образец: соответствующие файлы Spravochnik. DoD: единственное место с SQL каталога (grep); CRUD каталога работает.
- **T2.4 Таблицы УП (alembic).** `curriculum_plan` + `curriculum_project` (колонки 1:1 с `CURRICULUM_COLUMN_ALIASES` из текущего `curriculum.py`). Образец: `api/routers/curriculum.py` (алиасы колонок). DoD: миграция, FK, индексы; тест round-trip записи.
- **T2.5 CRUD-роутер УП.** `GET/POST/PUT/PATCH/DELETE /curriculum/plans[/{id}]`, `.../projects/{id}`. Образец: любой готовый роутер CG. DoD: УП создаётся/правится/читается из БД; тесты роутера.
- **T2.6 Editor-панель УП.** Каскад Направление→Блок→Проект, инлайн-правка, импорт CSV (первичное наполнение), экспорт CSV из БД. Образец: `CurriculumContext` (структура каскада) + существующая дашборд-оболочка. DoD: панель рендерится, правка персистится в БД.
- **T2.7 export.py.** `UPSkeleton`/`CurriculumExportV1` (JSON) + генерация 22-колоночного CSV из него. Образец: формат CSV из `КПшки/`. DoD: CSV — производное от JSON; round-trip тест (JSON→CSV→JSON эквивалентен).
- **T2.8 Генератор тянет УП из БД.** `repo.get_context(plan_id, project_order)->CurriculumContext` заменяет разбор CSV в памяти. Образец: текущая сборка `CurriculumContext`. DoD: генерация на УП из БД (не из CSV); e2e-тест.

## Волны 3–7 — крупные группы (детализировать при входе в волну)

- **W3–4 generator/ + translator/** (бюджет generator ≤10000, translator ≤2500). Агенты худеют (промпты→`prompts/`, парсинг→`structured`); 4 слоя оркестрации → один `engine.py`; удалить Jaccard-граф (`content_gen/curriculum/graph.py`); перенести перевод (doc+video). DoD: e2e-генерация на УП из БД даёт README ≥ прежнего качества; перевод doc+video работает; бюджет агентов соблюдён.
- **W5 checker/ (две оси)** (≤3000). `signals.py` (единый: повторы/таблицы/диаграммы — кормит обе оси), структурная ось = `readme_structure`+`document_integrity`, дидактическая = жюри (PoLL) + debate; подключить обе к `gate.evaluation`. DoD: оси раздельны (не складываются); HARD/abstain → `human_review_required`; на эталонном «битом» README ловятся дефекты.
- **W6 reference/ + UI-финал** (reference ≤1500, static ≤5000). Свернуть `viewer/app.py` (7595) в тонкий reference-модуль поверх общих таблиц; распилить `main.js` (7702) по модулям; финальная эстетика дашборда. DoD: справочник читается/правится из общей БД; все 5 плиток рабочие.
- **W7.1 Human-in-the-loop revision loop.** Перенести ревизионную подсистему CG: `methodology/{scoped_revision.py,assistant.py,change_request.py,checkpoint.py}` → `core/methodology/revision/` + repo-адаптер PG. Файлы: ≤2200 после удаления дублей, без потери сценариев. Образец: `legacy/Content_generator/content_gen/methodology/{scoped_revision.py,assistant.py,change_request.py,checkpoint.py}`. DoD: `ChangeRequest` создаётся из gate critical/human review; scoped revision применяет правку только в выбранном диапазоне; checkpoint сохраняет/восстанавливает артефакт; тесты clean + конфликт диапазона + rollback.
- **W7.2 Reverse-extraction → catalog reconciliation.** Обратное извлечение сверяется с каталогом и пишет предложения в review queue/каталог, не создавая дубликаты competency. Образец: текущий `reverse_extraction` CG + `review_queue` схемы Справочника. DoD: новый найденный competency идёт в review queue; совпадение по alias/provenance связывается с существующим competency_id.
- **W7.3 CI-гейты.** Включить `line_budget.yaml`, grep-гейты и дубль-детектор из AGENTS §CI. DoD: CI падает на нарушениях; есть тесты/fixtures на каждый запрет.
- **W7.4 Архив legacy.** Пометить legacy-репозитории archived после закрытия функционального parity. DoD: в docs зафиксирован parity checklist; legacy больше не является источником runtime-кода.

---

## Сквозные задачи (сделать в волне 0, проверять всегда)

- **TX.1 line_budget.yaml** на пакет (значения из `CONSOLIDATION_PLAN §2`). DoD: CI падает на PR сверх бюджета без `budget-override:`.
- **TX.2 grep-гейты** (pre-commit + CI): inline-промпты вне `prompts/`; сырой SQL вне `*/repo.py`/`core/db/`; import-циклы `core→modules`; ключ хука `on:` в `skill.yaml` (должен быть `at:`). DoD: гейты включены, тест на каждом запрете.
- **TX.3 Дубль-детектор** (`jscpd` или аналог) на py+js, порог < заданного. DoD: прогон в CI.
