# План консолидации: Spravochnik + Content_generator_ver2.4 → единая модульная система

> Обновление предыдущего 8-волнового плана под три новых требования:
> модульный UI с плитками, УП как редактируемая сущность БД, и две оси проверки из ноутбуков.
> Все пути и цифры ниже сверены с текущим состоянием обоих репозиториев (clone на дату плана).

---

## 0. Что мы имеем сейчас (факты из кода, не из памяти)

| | Content_generator_ver2.4 | Spravochnik |
|---|---|---|
| Стек | FastAPI + alembic + ваниль-JS | Flask (монолит-вьюер) + SQLite |
| Код (.py без тестов) | **~53 000** | **~17 900** |
| Тесты | ~11 100 | ~2 000 |
| JS | ver1: `main.js` ~2 722 + уже модульные `js/modules/*`; ver2.4-монолит 7 702 не является текущим донором UI | — |
| Самое тяжёлое | `agents/` 13 661, `api/` 11 102, `validators/rubric/` 6 860, `methodology/` 3 619 | `viewer/app.py` **7 595**, `pipeline/` 7 551 |
| БД | Postgres-готов, alembic (9 миграций), `api/db/` | SQLite, `scripts/build_catalog_db.py` |

**Что уже сделано в CG (и это важно):**
- Дашборд с плиточным паттерном уже есть: `goToGenerator()`, `goToChecker()`, `goToTranslator()` в `static/app.html` + `main.js`. **Плитки УП и справочника — чистое расширение этого паттерна, а не новый UI.**
- Роутеры-модули: `generation.py`, `readme_check.py`, `readme_translate.py`, `readme_improvement.py`, `curriculum.py`, `reverse_extraction.py`, `metrics.py`.
- `MethodologyGate` (`methodology/gate.py`) со стадией **`evaluation`** и методом `_review_evaluation`, который читает `rubric_json` из контекста и поднимает `human_review_required` на critical. **Это готовая точка подключения обеих осей.**
- Богатая модель `CurriculumContext` (блок, соседи, кросс-блок, SJM, expert notes) в `content_gen/models/curriculum.py`.
- `content_gen/didactics/` (composer/loader/manifest) — это **композиция дидактики при генерации** (праймит генератор), НЕ ось оценки. Ноутбуки добавляют именно **ось оценки**.

**Три разрыва, которые закрывает консолидация:**
1. **УП не персистится.** `api/routers/curriculum.py` парсит загруженный CSV транзитно и автозаполняет форму. Нет таблицы, нет редактирования, нет «подтянуть из БД». А *генерится* УП вообще в Spravochnik (`stage_dag_to_up.py`, `curriculum/planner.py`) — петля разорвана через ручной CSV.
2. **Идентичность навыка теряется на границе.** CG строит curriculum-граф через Jaccard по сырым строкам (`content_gen/curriculum/graph.py`), потому что из Справочника приходит CSV без `skill_id`/Bloom/рёбер.
3. **Структурная ось раздута и частично сломана.** `validators/rubric/` — это императивные чекеры (`toc_checker` 46 КБ, `chapter1-3` по 37–44 КБ, `annotation` 27 КБ ≈ **5 000 строк**), дублирующие `didactics/readme_strcture.json`. Ноутбук `structural_criteria_v2` показал: часть критериев тавтологична (2.4.7 всегда=1), часть ложно-срабатывает (2.4.6 ловит «примерно»).

---

## 1. Принципы (сквозные, ради «компактно, но без потери функционала»)

1. **Модуль = вертикальный срез.** Один фолдер модуля содержит всё своё: router + service + (опц.) pipeline + UI-панель + модели + таблицы. Добавить модуль = создать фолдер и зарегистрировать его. Это прямой ответ на «легко добавлять новые модули».
2. **Ядро не знает о фичах.** `core/` (db, llm, models, config, methodology, ui-kit) не импортирует ничего из `modules/`. Зависимость только в одну сторону.
3. **Переиспользовать, не дублировать.** Один LLM-клиент, один gate, один alembic, один набор эвристических сигналов (повторы/таблицы/диаграммы живут в ОДНОМ месте и кормят обе оси).
4. **Факты ↔ решения.** Модель/поиск предлагают; детерминированные правила и пороги решают. Дорогие шаги (поиск, жюри, дискуссия) — только по серой зоне.
5. **Две оси не складываются.** Структурная (скрипт, гейт «не сломано») и дидактическая (жюри, «хорошо ли преподано») — раздельные числа. `39/39` при `2.6/5` — валидный результат.
6. **Декларативное вместо императивного.** Структура README живёт в `readme_strcture.json`, а не в 5 000 строк python-чекеров. Чекер читает данные, а не хардкодит их.
7. **Контракт вместо прямого доступа к БД между слоями.** `ProfilePackage`/`UPSkeleton` — типизированная граница каталог↔генератор.

**Анти-Codex доктрина (закреплена в CI, раздел 8):** на каждый пакет — `line_budget.yaml`; grep-запреты на inline-промпты и сырой SQL вне repo-слоя; правило «одна Codex-сессия = одна волна = один модуль»; PR, превышающий бюджет, не мёржится без явного override.

---

## 2. Целевая структура монорепо

Эволюция конвенций CG (FastAPI-роутеры + content_gen-сервисы + static), а не стройка с нуля.

```
app/
├── core/                         # ЯДРО — общий код, без знания о фичах
│   ├── db/                       # session, Base, репозитории общего назначения      (~1500)
│   ├── llm/                      # ОДИН client + structured(complete_typed) + observe + prompts-loader  (~1500)
│   ├── models/                   # общие pydantic: skill, bloom, curriculum, profile_package           (~1500)
│   ├── config/                   # settings + config-as-data (пороги, allowlist колонок)                (~400)
│   ├── methodology/              # gate, decision, trace, checkpoint — позвоночник                       (~2500)
│   └── ui/                       # общие JS-утилиты, MODULE_REGISTRY, базовый CSS (s21-design)           (~1200)
│
├── modules/                      # ТОЧКА РАСШИРЕНИЯ — один фолдер на модуль
│   ├── generator/                # router + engine(один!) + агенты + panel.{html,js}                     (~10000)
│   ├── checker/                  # ДВЕ ОСИ: signals + structural(из ноутбука) + didactic-jury + panel    (~3000)
│   ├── translator/               # doc + video перевод (агент + субтитры + router)                       (~2500)
│   ├── curriculum/               # УП: catalog-pipeline + planner + persistence + editor-panel            (~5000)
│   └── reference/                # справочник: read/edit поверх общих таблиц каталога                     (~1500)
│
├── static/                       # оболочка дашборда (плитки) + подключение panel.js модулей
├── migrations/                   # alembic — ОДНА цепочка
└── tests/                        # зеркалит modules/ + core/                                              (~8000)
```

**Контракт модуля** (`modules/<name>/manifest.py`) — то, что делает «добавить модуль» механическим:

```python
MODULE = ModuleManifest(
    id="curriculum",
    title="Учебный план",
    icon="map",
    router=router,                 # FastAPI APIRouter с префиксом /curriculum
    ui_panel="curriculum/panel.html",
    tables=["curriculum_plan", "curriculum_project"],   # для alembic-аудита
    dashboard_tile=Tile(action="goToCurriculum", subtitle="Подготовка и правка УП"),
)
```

Дашборд при старте собирает плитки из `MODULE_REGISTRY` → новая плитка появляется автоматически. Никакого ручного редактирования `app.html` под каждый модуль.

**Бюджет:** ~30–32 тыс. строк прикладного кода (сейчас ~81 тыс. вместе с JS). Не цель «сжать ради сжатия» — цель убрать дублирование и императивщину; функционал переносится весь.

---

## 3. Карта переноса (current → target) с действиями компактизации

### 3.1 → `core/` (волна 1)

| Источник | Цель | Действие |
|---|---|---|
| `content_gen/llm/` (1 272) | `core/llm/client.py`, `observe.py` | За основу CG-клиент. В observe — единая запись: run_id, stage, prompt_version, model, tokens, latency |
| разбросанные `_safe_json_extract` в агентах | `core/llm/structured.py` (новый) | ОДИН `complete_typed(prompt, schema)->BaseModel` с repair-retry. Локальные парсеры удаляются на волне 3 |
| inline-промпты во всех агентах + стадиях | `core/llm/prompts/<area>/<name>@v1.md` | Механический вынос строк в файлы; версия из имени файла → в лог |
| `content_gen/models/` (2 213) + `Spravochnik` skill-модели | `core/models/` | Слить две модели навыка в одну. `ProfilePackage`/`UPSkeleton` — здесь |
| `content_gen/methodology/gate.py` + harness | `core/methodology/gate/` + `core/methodology/{harness.py,rules.py}` | Gate/harness переносятся в волне 1: deterministic review, trace-friendly contracts, без знания о модулях |
| `content_gen/methodology/{scoped_revision.py,assistant.py,change_request.py,checkpoint.py}` | `core/methodology/revision/` | Human-in-the-loop петля правок переносится отдельной задачей W7.1, чтобы не смешивать gate с механизмом ревизий и не потерять scoped revision/checkpoint |
| `content_gen/config/` (317) + `thresholds` из ноутбука | `core/config/settings.py` + `thresholds.yaml` | **Единственный источник правды по порогам.** Пороги из `structural_criteria_v2` (`annotation_chars`, `readability_band`, `repetition_ratio_max`, …) переезжают сюда, синхронизируются с `CRITERIA.md` |

### 3.2 → `modules/generator/` (волны 3–4, лимит 10 000)

Самая большая трансформация. Сейчас `agents/` 13 661 + четыре слоя оркестрации.

| Источник | Действие компактизации |
|---|---|
| `agents/*.py` (44 файла) | Худеют за счёт выноса промптов (`core/llm/prompts/`) и парсинга (`core/llm/structured`). `formula_table.py` (1 100), `intro_rules.py` (716), `dataset_generator.py` (611) — режутся вдвое после выноса строк |
| 9× `practice_*`-логики (practice, practice_critic, practice_repair, practice_contracts, …) | Схлопнуть в 3–4 связных файла `practice/` внутри модуля |
| `orchestrator_phases_modules/` + `flow.py` + recovery + regeneration | ОДИН `engine.py` (фазы как данные, не как 4 параллельных слоя) |
| `content_gen/curriculum/graph.py` (Jaccard-граф) | **Удаляется.** Граф приходит из `modules/curriculum` с настоящими `skill_id`/рёбрами, а не пересобирается по строкам |
| `recovery/` (77), `regeneration.py` (538) | Растворяются в engine как стратегии retry |

**Интеграция УП в генератор (ключевое требование):** `generator/service.py` получает `CurriculumContext` **из БД через `modules/curriculum`** (по `plan_id` + `project_order`), а не из разобранного CSV. Форма генерации подтягивает каскад Направление→Блок→Проект из персистентного УП.

### 3.3 → `modules/checker/` (волна 5, лимит 3 000) — ДВЕ ОСИ

Здесь живёт новый слой критериев из ноутбуков. Заменяет `validators/rubric/` (6 860) и достраивает дидактику.

```
modules/checker/
├── signals.py        # ЕДИНЫЙ источник эвристик: repetition_ratio, near_dup,
│                     #   broken_tables, diagram_topic_match. Кормит ОБЕ оси.       (~150)
├── structural.py     # Ось 1 из structural_criteria_v2: PREFLIGHT + KEPT + FIXED + NEW (~600)
│                     #   registry-подход вместо 5000 строк section1-4 checkers
├── didactic/         # Ось 2 из didactic_quality_check_jury
│   ├── dimensions.py #   6 дименшенов + рубрика                                     (~120)
│   ├── jury.py       #   PoLL: N моделей → медиана, генератор исключён             (~250)
│   ├── debate.py     #   эскалация critic/defender/judge (разные модели)          (~200)
│   └── report.py     #   DidacticScore/Report, abstain-логика                      (~120)
├── service.py        # собирает обе оси → rubric_json + didactic_json              (~200)
├── router.py         # /check (на готовом README), переезд из readme_check.py     (~150)
└── panel.{html,js}   # модалка чекера (UI уже есть: checker.html)                 (~500)
```

**Что конкретно меняется по структурной оси (из ноутбука):**
- `validators/rubric/{toc,chapter1,chapter2,chapter3,annotation}_checker.py` (~5 000 строк) → **удаляются**, заменяются registry на ~600 строк.
- **FIXED:** читабельность 2.4.7 — честная формула Флеша-Оборнева вместо тавтологичной нормировки `[0,30]→[50,80]` (критерий теперь МОЖЕТ упасть); детектор примера 2.4.6 — по границам слова + маркер `**Пример**` (больше не ловит «примерно/применять»); определения 2.4.4 → SOFT.
- **PREFLIGHT** (P.1–P.6, бывшие 1.1–1.6) выносятся из балла качества в гейт «структура не сломана». Сливается с уже существующим `validators/structural_preflight.py` (219).
- **NEW** (N.1–N.5): целостность таблиц, дословные повторы (template bleed), диаграмма↔тема, оборванные фразы/кавычки, единый project-id — ловят то, что 39 критериев пропускали.
- HARD-провал → issue в `MethodologyGate._review_evaluation` → `human_review_required`.

**Что конкретно по дидактической оси (из jury-ноутбука):**
- 6 дименшенов 1–5: связность, scaffolding, качество примеров, когнитивная нагрузка, тон p2p, не-AI-водность.
- **Жюри (PoLL):** ≥2 разных модели → медиана; разброс → confidence. **Генератор исключается из жюри** (анти-self-bias) — слаг берётся из `GENERATOR_MODEL`.
- Эскалация спорных/проваленных дименшенов (`confidence<0.55` или `score<3.0`) в дискуссию critic/defender/judge на РАЗНЫХ моделях.
- Отказ вместо ложного балла → `needs_human_review` → тот же gate.
- `overall_calibrated=None` пока нет экспертного набора (см. раздел 9, долг).

**Анти-дублирование (конкретный выигрыш):** эвристики повторов/таблиц/диаграмм сейчас задублированы в обоих ноутбуках И пересекаются со структурными NEW-проверками. В модуле они живут **однажды** в `signals.py`: структурная ось использует их как HARD-гейты целостности, дидактическая — как evidence для дименшенов.

### 3.4 → `modules/translator/` (волна 4, лимит 2 500)

| Источник | Действие |
|---|---|
| `agents/translator.py` (841), `subtitles/` (962), `api/routers/readme_translate.py` (24 КБ) | Перенос в модуль. Промпты → в `core/llm/prompts/translator/`. Видео-пайплайн (ASR→перевод→TTS→mux) как был — он детерминирован |

### 3.5 → `modules/curriculum/` (волна 2, лимит 5 000) — УП КАК СУЩНОСТЬ БД

Сюда переезжает пайплайн каталога Spravochnik (7 551) + персистентность УП.

| Источник | Цель | Действие |
|---|---|---|
| `stage_brief_to_catalog.py` (1 219), `stage_atomize.py`, `stage_normalize.py`, `stage_catalog_to_dag.py`, `stage_dag_to_up.py` (759) | `curriculum/stages/` | Перенос почти как есть. Замены: модели из `core`, LLM через `core/llm/structured`, конфиг из settings |
| `pipeline/curriculum/planner.py` (610) + `domain.py` (спиральный планировщик) | `curriculum/planner/` | Без изменений логики — детерминирован, реализует Брунера/Хардена/Хэтти |
| `competency_catalog.py` (1 001), `storage.py` (1 598) | `curriculum/repo.py` | Слить в один repo-слой. **SQLite → Postgres** (та же схема, alembic). Единственное место с SQL каталога |
| `up_template_consilium.py` | `curriculum/consilium.py` | `ALLOWED_ARTIFACT_FAMILIES` экспортируется — нужен генератору |
| — (новый) | `curriculum/export.py` | Выпуск `UPSkeleton`/`CurriculumExportV1` (JSON) + генерация 22-колоночного CSV из него же. **CSV становится производным представлением для людей, а не каналом данных** |
| `tests/test_regression_pipeline.py` (2 005) | `tests/curriculum/` | Приёмочный тест волны — адаптировать импорты |

**Персистентность УП (закрывает требование №1):**
- Новые таблицы (alembic): `curriculum_plan` (направление, версия, статус, автор, created/updated) и `curriculum_project` (FK→plan, order, block_name, title, description, learning_outcomes[], skills[], audience_level, required_tools[], sjm, workload_hours, group_size, platform_name, …) — DB-контракт `CURRICULUM_ALIAS_FIELD_TO_COLUMN`; CSV-алиасы живут отдельно в `CSV_COLUMN_ALIASES`.
- CRUD-роутер: `GET/POST/PUT/PATCH/DELETE /curriculum/plans[/{id}]`, `.../projects/{id}`. УП **редактируем** через panel.
- `editor`-панель: каскад Направление→Блок→Проект (UI уже спроектирован в `CurriculumContext`), инлайн-правка ячеек, импорт CSV (через существующий парсер) как способ *первичного наполнения*, экспорт CSV из БД.
- Старый `POST /curriculum/upload` (CSV→форма) сохраняется как «импорт в БД», а не как единственный путь.
- **Генератор подтягивает УП из БД:** `curriculum/repo.get_context(plan_id, project_order) -> CurriculumContext` заменяет разбор CSV в памяти.

### 3.6 → `modules/reference/` (волна 6, лимит 1 500) — СПРАВОЧНИК

| Источник | Действие |
|---|---|
| `Spravochnik/viewer/app.py` (**~6 978** в текущем legacy), монолит path-dispatch | **Сворачивается** в тонкий read/edit модуль поверх ОБЩИХ таблиц каталога. Не переписывать схему (она сильная: provenance, alias-нормализация, `ai_analysis_*`, `review_queue`) — только сменить транспорт на FastAPI-роутер + panel |
| `viewer/templates/`, `viewer/static/` | `reference/panel.{html,js}` | Тонкий просмотр/правка навыков, компетенций, индикаторов, графа |
| `Spravochnik/КПшки/`, `scripts/`, `sql/`, artifacts | — | **НЕ переносятся:** отработавшие миграции, бинарники, данные. Данные — в Postgres, не в git |

### 3.7 → `static/` (волны 4–6)

| Источник | Действие |
|---|---|
| `main.js` ver1 (**~2 722**) + уже готовые `js/modules/*` | Не пилить как ver2.4-монолит: переселять готовые модули в `app/static/<module>/panel.js`, общий dashboard оставлять thin shell по `MODULE_REGISTRY` |
| `новый дизайн/` (design-canvas.jsx, index.html, styles.css, «Генератор · standalone.html») | Целевая эстетика дашборда. Свести к `s21-design.css` + плиточная оболочка |
| `app.html`, `checker.html`, `translator.html` | Оболочка остаётся; плитки рендерятся из `MODULE_REGISTRY` |

**budget-override: static_ui ≤12 000.** Старый лимит 5 000 слишком низкий для пяти живых панелей и
общей дизайн-системы: ver1 frontend без minified vendor и бинарных ассетов примерно 24k строк
(`css` ~11.4k, `js/modules` ~6.5k, `main.js` ~2.7k, `html` ~3.3k). 5k остаётся запахом скелета,
не guardrail. `vendor/mermaid.min.js` не портируется и не считается в бюджет; Mermaid подключается как
внешняя dependency/CDN. `land.png` — бинарный ассет, не source line budget.

**W6 decomposition:** порядок и промпты живут в `docs/W6_UI_PORT.md`: R1 reference service (поверх
`CurriculumCatalogRepo`, без второго каталога) → U1 дизайн-система → U2 оболочка+markdown → U3 generator →
U4 checker → U5 translator → U6 reference panel parity → U7 финальный e2e. Curriculum panel уже готова в T2.6,
поэтому W6 переносит 4 панели, а U7 проверяет 5/5 плиток.

---

## 4. Подключение двух осей к gate (точная механика)

Сейчас `gate._review_evaluation` (gate.py:567) читает `context["rubric_json"]`. Расширяем симметрично:

```
engine финализация → checker.service.evaluate(readme, learning_outcomes) →
    {
      "rubric_json":   structural.run(md),        # ось 1, HARD-fails
      "didactic_json": didactic.judge(md, los),   # ось 2, abstain/below-floor
    }
→ gate._review_evaluation:
    - structural HARD-fail        → critical issue → human_review_required
    - didactic needs_human_review → review issue   → human_review_required
    - ДВА ЧИСЛА НЕ СКЛАДЫВАЮТСЯ — оба в trace, оба в final-metrics UI
```

UI финальных метрик (`final-metrics-ui.png`) показывает обе оси раздельно: структурный гейт (зелёный/возврат) + дидактический профиль по 6 дименшенам с пометкой эскалаций.

---

## 5. Единая БД (Postgres, одна alembic-цепочка)

- Базис — alembic CG (9 миграций уже есть). Схема Справочника **переносится в ту же цепочку** (а не остаётся отдельной SQLite).
- Новые миграции: (a) таблицы каталога Справочника; (b) `evidence_source`, `profile_brief`, `skill_prerequisite` (три недостающие таблицы из прошлого плана); (c) обобщение `ai_analysis_run` с проекта на любой entity; (d) `curriculum_plan`/`curriculum_project` (персистентный УП).
- `core/methodology/checkpoint.py` и `api/db/*` уже умеют Postgres — переиспользуем session/Base.

---

## 6. Волны миграции (последовательно, с критерием готовности)

> Правило: одна волна = одна Codex-сессия со своим `line_budget`. Не начинать N+1, пока приёмочный тест N не зелёный.

| Волна | Содержание | Definition of Done |
|---|---|---|
| **0. Каркас** | Завести монорепо-структуру, `MODULE_REGISTRY`, пустые модули с manifest, alembic-базис, перенос схемы Справочника в Postgres | Дашборд поднимается, плитки рендерятся из реестра (пустые), `alembic upgrade head` чистый |
| **1. core/** | llm(client+structured+observe+prompts-loader), models(слияние skill), methodology, config(+thresholds.yaml) | `complete_typed` работает; gate проходит свои тесты; нет inline-промптов (grep-гейт) |
| **2. curriculum/** | Перенос пайплайна каталога, планировщик, repo (SQLite→PG), **таблицы УП + CRUD + editor-panel**, export(JSON+CSV) | `test_regression_pipeline` зелёный на PG; УП создаётся/правится/читается из БД; CSV — производное |
| **3–4. generator/ + translator/** | Агенты худеют (промпты/парсинг наружу), 4 слоя оркестрации→`engine.py`, удалить Jaccard-граф, **генератор тянет `CurriculumContext` из БД**, перенос перевода | Генерация e2e на УП из БД даёт README ≥ прежнего качества; перевод doc+video работает; бюджет агентов соблюдён |
| **5. checker/ (две оси)** | `signals.py` (единый), `structural.py` (из ноутбука, удалить section1-4 checkers), `didactic/` jury+debate, подключить обе оси к gate | Структурная ось ловит N.1–N.5 на эталонном «битом» README; дидактика даёт раздельный профиль; HARD-fail/abstain поднимают `human_review_required` |
| **6. reference/ + UI-финал** | R1/U1–U7 из `docs/W6_UI_PORT.md`: reference поверх общего repo; перенести ver1 `js/modules/*` в 4 панели (curriculum уже есть); dashboard оставить thin shell. Static budget-override: ≤12k, без vendor/minified и бинарных ассетов | Справочник читается/правится из общей БД; все 5 плиток ведут в живые панели с реальными endpoint calls; UI не является набором пустых `panel.html` |
| **7. Петля и архив** | Human-in-the-loop revision loop (scoped revision/change request/checkpoint), reverse-extraction сверяется с каталогом (обратное извлечение → реконсиляция), архив legacy-репозиториев | Правки проходят через change request + scoped revision + checkpoint/rollback; обратная связь замкнута; старые репо помечены archived; CI-гейты включены |

---

## 7. Шесть рецептов компактизации (применять механически)

1. **Inline-промпт → версионированный файл.** Строка в python → `core/llm/prompts/<area>/<name>@v1.md`, версия из имени → в observe-лог.
2. **Локальный JSON-парсер → `structured.py`.** Любой `_safe_json_extract`/`re.search("{.*}")` → `complete_typed(prompt, schema)`.
3. **Регэксп-валидация Mermaid → headless-рендер.** Проверять диаграмму рендером, а не регэкспом (как N.3 в ноутбуке — токенная эвристика + рендер).
4. **SQL в хендлере → repo-слой.** Любой сырой SQL вне `*/repo.py` или `core/db/` — нарушение.
5. **Решение LLM о структуре → детерминированная политика.** «Куда вставить формулу/пример» — не во время генерации моделью, а `MediaPlanV1` из домен-тегов + artifact family + Bloom (upstream, детерминированно).
6. **N мелких связанных файлов → один связный модуль.** 9× `practice_*` → `practice/` (3–4 файла); section1-4 checkers → один registry.

---

## 8. CI-гейты против раздувания (Codex любит дублировать)

- **`line_budget.yaml`** на пакет: PR, превышающий бюджет модуля, падает в CI без явного `budget-override:` в описании PR.
- **grep-запреты** (pre-commit + CI): inline-промпты (длинные строки с маркерами роли) вне `prompts/`; сырой SQL вне repo-слоя; `import`-циклы `core → modules`.
- **`CLAUDE.md`/`AGENTS.md`** в корне: «одна сессия = одна волна = один модуль; не трогать чужие модули; перед добавлением функции — grep, нет ли её».
- **Дубль-детектор:** прогон `jscpd`/аналога на python+js, порог дублирования < заданного.
- Приёмочный тест каждой волны (раздел 6) — обязательный gate.

---

## 9. «Не переносить» — лог (~25 000 строк уходит)

- `validators/rubric/{toc,chapter1,chapter2,chapter3,annotation}_checker.py` (~5 000) → registry ~600.
- `content_gen/curriculum/graph.py` (Jaccard-граф) → граф из каталога.
- 4 слоя оркестрации → один `engine.py`.
- `Spravochnik/viewer/app.py` (7 595) → тонкий reference-модуль.
- `Spravochnik/{КПшки,scripts,sql,artifacts}`, отработавшие миграции, бинарники, CSV-данные → в БД/хранилище, не в git.
- Дубли: два LLM-клиента → один; две модели навыка → одна; эвристики из двух ноутбуков → один `signals.py`.

---

## 10. Долги, которые нельзя замолчать (из самих ноутбуков)

1. **Полоса читабельности `(45, 80)` — провизорная.** Калибровать на 30–50 реальных README по экспертной оценке комфортности. Сейчас разумная заглушка, не истина.
2. **Дидактика не калибрована.** `overall_calibrated=None`, пока нет экспертного набора 30–50 README (включая «39/39, но забраковано»). Любой балл до этого — вера, не измерение.
3. **Состав жюри подбирается по данным, не угадывается.** Измерить согласие каждой модели с экспертом по каждому дименшену (QWK/Spearman/ICC), выкинуть плохие. Единого «лучшего судьи» нет.
4. **Item-анализ структурных критериев.** Прогнать набор, выкинуть критерии с нулевой дискриминацией (всегда =1).

---

## 11. Решения до старта — ЗАКРЫТО → см. `DECISIONS.md`

Пять пунктов закрыты (ADR в `DECISIONS.md`). Кратко:

1. **`assumed_known`** — явный, из каталога: `[]` для бассейна / outcomes предыдущих веток («ветка из ветки», 3.1.1). `audience_level` produces в контекст.
2. **Гранулярность графа** — компетенции (52 скилла); концептный слой отложен (аддитивно позже). **Закрыто полностью.**
3. **Часы** — оценивается только X (человеко-часы); `days=round(X·0.34)+3`, `xp=X·10` (3.1.3). 11 дедлайнов, 3 проверки/проект.
4. **Жюри** — ≥3 вендор-разные модели, генератор исключён; правило+дефолт закрыты, **слаги OpenRouter — подтвердить**.
5. **Справочник** — общий PG с старта (схема едет на T0.4); `ProfilePackage` — in-process контракт, не сетевой API.

Не блокирует волны 0/1/M. Открытые «подтвердить» (baseline бассейна, `hours_band`, слаги, живой ли viewer) — в `DECISIONS.md`, всплывают на T0.4 / волне 2 / волне 5.

---

## Итог

Это не «слить два репо», а **собрать одну модульную систему**: ядро (`core/`) + вертикальные модули-фичи (`modules/`), где дашборд CG с плитками — оболочка, а добавление модуля = фолдер + регистрация в `MODULE_REGISTRY`. Пять плиток: генератор, чекер (две оси), переводчик, **УП (персистентный, редактируемый, кормит генератор из БД)**, справочник. Новый слой критериев из ноутбуков встаёт как `modules/checker`: структурная ось — компактный registry (−5 000 строк императивщины, +исправленные критерии), дидактическая — жюри моделей с дискуссией и отказом, обе подключены к одному `MethodologyGate.evaluation` и НЕ складываются. Перенос — по волнам с приёмочным тестом на каждой; компактность держится бюджетами и CI-гейтами, а не разовой чисткой. Функционал переносится весь; уходит только дублирование и мёртвый код (~25 000 строк).
