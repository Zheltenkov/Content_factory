# START_HERE.md — рабочий гайд по миграции (Content_factory)

> Корень репо. Структура: `AGENTS.md` (читается Codex автоматически), `docs/` (спека, план, задачи,
> решения, регламенты, ноутбуки, эталоны), `legacy/` (исходники ver1, видны Codex), `app/` (сборка).

## Где мы сейчас
- **Волна 0 — код готов:** T0.1 каркас, T0.2 registry+плитки, T0.3 alembic-цепочка (12 ревизий из CG),
  T0.4 схема Справочника (013) + таблицы УП (014). Осталось закрыть строгий DoD: прогнать `alembic upgrade head` на живом PG
  (Codex-cloud до localhost не достучится — запускай ЛОКАЛЬНО; см. низ файла).
- **Волна 1 — core готова:** harness/rules, LLM core, unified models, MethodologyGate, config/thresholds.
- **Волна M — methodology готова до TM.4:** TM.1 эталоны, TM.2 базовые скиллы, TM.3 kids/commerce,
  TM.4 thin engine→harness→gate (`app/modules/generator/engine.py`).
- **Волна 2 начата:** T2.1 curriculum catalog pipeline перенесён в `app/modules/curriculum/stages/`,
  T2.2 spiral planner подключён к `stage_dag_to_up`, T2.3 repo-слой каталога перенесён в
  `app/modules/curriculum/repo.py`, T2.4 добавил PG-таблицы УП `curriculum_plan`/`curriculum_project`
  и round-trip `UPSkeleton` через repo, T2.5 добавил CRUD API, T2.6 добавил editor-панель УП,
  cascade API и CSV import/export, T2.7 добавил `curriculum/export.py`: `CurriculumExportV1`
  и 22-колоночный CSV как производное от JSON, T2.8 добавил DB-backed `CurriculumContext`
  (`repo.get_context(plan_id, project_order)`) и generator endpoint `/generator/runs/from-curriculum`.
- **W3–4 начата:** G1 orchestration spine перенесён в существующий `app/modules/generator/engine.py`
  (`domain.py` contracts, workflow checkpoints, skip/conditions, LLM trace hook, gate bridge).
  G2 head добавил `generator.head`: title/annotation/intro/planning scaffold с typed draft и deterministic guards.
  Дальше — **G3 theory**.
  Порядок зависимостей: `0 → 1 ∥ M → 2 → (3,4) → 5 → 6 → 7`.

## Три правила, которыми держится результат (выстраданы)
1. **Одна задача = один прогон Codex.** Не «собери проект». После каждой — **пуш**, затем сверь `wc -l`
   результата против источника СВОИМИ глазами + спот-чек, что код реальный.
2. **Не верить только зелёным тестам.** Они могут быть зелёными на заглушке. Критерий — поведение против
   источника, а не число строк и не «N passed».
3. **legacy должен быть виден Codex.** Он уже загружен в `legacy/` и закоммичен. Страж источника в
   порт-промптах остановит, если что-то не на месте, — не даст генерить по памяти.

## Как ставить задачу
Codex сам читает `AGENTS.md`. Даёшь РОВНО один промпт за прогон. Для задач из legacy — промпт со стражем
ниже. Для не-портовых (скелет, скиллы из регламентов) — обычные промпты ниже.

---

## ПРОМПТ ПОРТА (для всех задач, тянущих из legacy) — со СТРАЖЕМ ИСТОЧНИКА
Главный антидот к скелету. Конкретные пути/строки под ver1 — в `docs/GENERATOR_CHECKER_PORT.md`.
```
ПОРТ <что> из legacy. ОДНА задача. Не брать следующую. Код ТОЛЬКО из прочитанного источника.
ШАГ 0 — СТРАЖ ИСТОЧНИКА (провал => СТОП, ничего не менять):
  Проверь, что <legacy/путь> существует и НЕ пуст; выведи его `wc -l`.
  Если нет/пусто -> напиши "LEGACY ОТСУТСТВУЕТ — ПОРТ НЕВОЗМОЖЕН" и остановись. НЕ генерируй по памяти.
ШАГ 1 — прочитай источник целиком <legacy/путь>; AGENTS.md; строку задачи в docs/TASKS.md.
ШАГ 2 — перенеси РЕАЛЬНУЮ логику в <app/путь>, компактизируя по AGENTS (промпты->prompts/, модели->core,
  без дублей), НЕ выкидывая функционал. Упёрся в бюджет -> СТОП и сообщи (не стабь, чтобы влезть).
ШАГ 3 — тест под РЕАЛЬНОЕ поведение (не под заглушку): обычный кейс + граничный.
ШАГ 4 — покажи `wc -l` источника и результата; вывод теста; что НЕ перенёс и почему.
DoD: объём сопоставим с источником (ориентир ~40-60%; <30% — почти наверняка скелет, объясни).
  Тест зелёный на реальной логике. Не брать следующую.
```

---

## Прогресс и готовые промпты

- [x] **T0.1 / T0.2 / T0.3 / T0.4** — Волна 0 (код). Закрыть строгий DoD = `alembic upgrade head` на PG.
- [x] **T1.1 / T1.2 / T1.3 / T1.4 / T1.5** — ядро.
- [x] **TM.1 / TM.2 / TM.3 / TM.4** — методслой, профили и bridge engine→gate.
- [x] **T2.1** — catalog intake stages: `brief -> competencies -> DAG -> UPSkeleton`.
- [x] **T2.2** — spiral planner: artifact-first packing, hard-DAG order, Bruner/Harden/Hattie repeats.
- [x] **T2.3** — curriculum catalog repo: CRUD skill/alias, resolver, competency links, review queue.
- [x] **T2.4** — persistent UP tables: `curriculum_plan` + `curriculum_project`, repo round-trip.
- [x] **T2.5** — CRUD API for persistent UP plans/projects.
- [x] **T2.6** — DB-backed curriculum editor panel with cascade, inline edit, CSV import/export.
- [x] **T2.7** — `CurriculumExportV1` JSON export plus 22-column CSV projection and JSON↔CSV round-trip.
- [x] **T2.8** — generator reads persisted UP context from DB via `repo.get_context(plan_id, project_order)`.
- [x] **G1** — generator orchestration spine: stage contracts, workflow snapshots/checkpoints, skip conditions,
  LLM observability hook, harness/gate bridge in the existing engine.
- [x] **G2** — generator head: title/annotation/intro/planning scaffold, TOC, project context analysis,
  typed LLM draft plus deterministic boundary guards.

### ▶ T1.1 + TM.1 — перенос методслоя (следующая; без legacy, делать вместе)
```
Реализуй T1.1 + TM.1 из docs/TASKS.md. Прочитай: AGENTS.md; T1.1, TM.1; docs/SKILLS_ARCHITECTURE.md §6.
Это ПЕРЕНОС из эталонов, логику не переписывать:
1. Скопируй docs/harness_ref/core/methodology/{rules.py,harness.py} и весь profiles/ в app/core/methodology/.
2. Влей реальный document_integrity: check.py из
   docs/document_integrity_skill/document_integrity/core/methodology/profiles/_base/skills/document_integrity/check.py
   -> app/core/methodology/profiles/_base/skills/document_integrity/check.py.
3. ИСПРАВЬ ключ хука в этом document_integrity/skill.yaml: `- on:` -> `- at:` (иначе harness падает).
4. Скопируй оба теста в tests/, поправь импорт-пути под app/.
DoD: pytest tests/test_harness.py tests/test_document_integrity.py — 10/10 зелёных. Не бери следующую.
```

### ▶ reference — ПЕРВЫЙ ПОРТ-ИНДИКАТОР (после методслоя)
Источник `legacy/Spravochnik/viewer/app.py` (7595 строк). Это проверка, что legacy реально читается:
если `app/modules/reference/service.py` вышел в тысячи строк, а не сотню — цикл со скелетами разорван.
Бери ПРОМПТ ПОРТА, `<legacy/путь>` = legacy/Spravochnik/viewer/app.py, `<app/путь>` = app/modules/reference/.

### TM.2.<n> — скиллы из регламентов (без legacy, по одному за прогон)
```
Реализуй TM.2.<n> — скилл <skill_id> (docs/TASKS.md таблица TM.2). Прочитай: AGENTS.md; строку <skill_id>
в docs/SKILLS_ARCHITECTURE.md §8.1; секцию <секция> в docs/regulations/osnova.md; ОДИН эталон в
docs/harness_ref/.../_base/skills/ (augment->voice; validate->visual_quality; producer->competency_weights).
Создай app/core/methodology/profiles/_base/skills/<skill_id>/: skill.yaml (ключ `at:`, namespaced-стадии,
severity/params по §8.1); instructions.md (если at: prompt.augment); check.py (если машинное правило,
def check(doc,params)->list[RuleIssue], <=150 строк; producer: def prepare(ctx,params)->dict);
tests/test_<skill_id>.py (чистый + битый). DoD: тест зелёный + harness резолвит _base. Не бери следующий.
```
Маппинг skill_id -> секция osnova.md: voice 3.2.4 | content_sufficiency 3.2.2 | branch_structure 3.2.1 |
audience_level 3.1.1 | software_constraints 3.1.2 | checklist 3.3 | repository_structure 3.5 |
autotests 3.7 | template_blocks 3.2.3 | workload_planning 3.1.3 | access_constructors 3.1.2.
(competency_weights — уже в harness_ref, перенести.)

### TM.3 — профили kids + commerce
```
Реализуй TM.3 из docs/TASKS.md. Прочитай: AGENTS.md; docs/SKILLS_ARCHITECTURE.md §8.2,§8.3;
docs/harness_ref/.../profiles/{kids,commerce} (каркас); docs/regulations/{deti,commerce}.md.
Допиши kids-оверлеи (program_types, lesson_structure, mentor_assets, assessments, student_portrait)
реальными instructions.md/check.py по образцу _base и регламента Дети (3.1.3, 3.2.4). commerce проверь.
DoD: harness резолвит kids (main/intensive/master_class) и commerce; producers_bound_to("generator.")==[]; тест.
```

### TM.4 — harness -> engine -> gate
```
Реализуй TM.4 из docs/TASKS.md. Прочитай: AGENTS.md; docs/SKILLS_ARCHITECTURE.md §4,§6;
docs/CONSOLIDATION_PLAN.md §4; app/core/methodology/{harness.py,gate/}.
Создай или обнови тонкий интеграционный слой в app/modules/generator/engine.py:
1. stage runner зовёт harness.prepare(stage, ctx) перед стадией;
2. harness.augment(stage, ctx) отдаёт инструкции стадии;
3. output стадии приводится к GeneratedDoc;
4. harness.validate(stage, doc, ctx) собирает RuleIssue;
5. RuleIssue сериализуются в rubric_json и передаются в MethodologyGate.review("evaluation", ctx).
DoD: e2e-тест активного профиля прогоняет prepare/augment/validate; HARD issue становится critical в gate и
поднимает human_review_required. Интеграционный слой <=300 строк. Не брать следующую.
```

### generator (G1…G5) и checker (C1…C4)
Полная разбивка на под-задачи с заполненными промптами и путями ver1 — в **`docs/GENERATOR_CHECKER_PORT.md`**.
Брать строго по одной. **Следующая: G3 theory** (`theory_*`, `theory_phase_executor`, `definitions_agent`,
`length_agent`, `readability_agent`) поверх G1/G2. checker — помни: в основном НЕ порт
(rubric заменяется скиллами), типы промптов там разные.

### Волны 2 (УП), 6 (UI), 7 (петля)
В `docs/TASKS.md`. Волна 2 атомарна; UI (W6) — отдельными задачами на panel.{html,js} модуля из
`legacy/Content_generator/static`. Перед волной 5 закрой `docs/DECISIONS.md D4` (слаги OpenRouter).

---

## Закрыть строгий DoD Волны 0 (нужен PG)
`alembic upgrade head` запускай ЛОКАЛЬНО (Codex-cloud не достучится до твоего PG).
Быстрый PG через Docker:
```bat
docker run --name cf-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=content_factory -p 5432:5432 -d postgres:16
```
В `.env`: `DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/content_factory`
Затем из корня: `alembic upgrade head` && `alembic current` (= 014). Без Docker — бесплатный Neon/Supabase,
строку подключения в `.env`. После успешного upgrade + проверки таблиц Волна 0 закрыта строго по DoD.
