# План: исправление и продолжение рефакторинга

> Корректирующий план поверх уже выполненной codex-консолидации. Опирается на факты из кода
> (на дату составления), а не на память. Дополняет `CONSOLIDATION_PLAN.md`, **отменяет**
> `UI_LEGACY_PARITY_AUDIT.md` в части split-shell.

## 0. Зафиксированные решения (ADR этого плана)

1. **UI-доктрина: единая оболочка + полный функциональный паритет.**
   Один S21-стиль (как на референс-скрине дашборда). Все 5 плиток в одном дашборде, один хедер,
   одна тема. Функционал всех 3 legacy-проектов (Content_generator, Spravochnik, Proverka)
   портируется в эту оболочку **до последней кнопки**, без потери поведения. Раздвоение оболочек
   («контур методолога» отдельным шеллом) — **отвергнуто**.
2. **«Аудитор» = модуль `checker`** (источник `legacy/Proverka/src/content_audit`), две оси:
   структурная + дидактическое жюри. Это та же плитка, что сейчас называется «Проверка».
   Допустимо переименовать ярлык плитки `Проверка → Аудитор` (одна строка в манифесте).
3. Источник истины по архитектуре — `CONSOLIDATION_PLAN.md`. Этот файл — корректирующий слой.

## 1. Что уже сделано (правда из кода)

- Монорепо-каркас `app/core` + `app/modules/{generator,checker,translator,curriculum,reference}` поднят.
- Реестр модулей (`app/core/registry.py`) + манифесты (`app/modules/__init__.py`) — **все 5 плиток
  регистрируются и рендерятся динамически**. Проверено: дашборд отдаёт 5 плиток.
- Alembic — одна цепочка до `018`. SQLite Справочника переехал в PG-схему.
- Статик-тесты UI зелёные.
- Legacy-маршруты Spravochnik (`/intake`, `/up`, `/catalog-admin/*`, `/competencies/*`,
  `/profiles/*`, `/reviews`) заведены в `app/main.py`.

## 2. Что дрейфануло (это и есть «непонятно на входе»)

| # | Проблема | Где | Действие |
|---|---|---|---|
| D1 | Два дока противоречат: unified vs split-shell | `UI_LEGACY_PARITY_AUDIT.md` | Переписать в матрицу фич-паритета под единой оболочкой; раздел «split shell» удалить |
| D2 | Дашборд-копия говорит «контур методолога» (язык split-shell) | `app/static/dashboard.html:37` | Переписать под единый контур |
| D3 | Legacy-маршруты Spravochnik отдают одну панель-заглушку, имитируя 2-й шелл | `app/main.py:103-141` | Свести к deep-link'ам внутри единой панели модуля (рендерят тот же shell), либо в SPA-роутинг панели; убрать намёк на отдельный методолог-контур |
| D4 | Плитка называется «Проверка», пользователь ждёт «Аудитор» | `app/modules/__init__.py:36` | Решить ярлык (см. ADR-2); если переименовываем — обновить тесты-парити |
| D5 | Текущий дашборд беднее референс-скрина: нет «Недавние запуски», service-meta (последний запуск, активные задачи) | `app/static/dashboard.html`, нет endpoint | Портировать как фичу (см. W-Gen) |

## 3. Дельта функционального паритета (бэклог «полный функционал»)

Источник — `UI_LEGACY_PARITY_AUDIT.md` (его *инвентарь* фич корректен и ценен; неверна только
его доктрина двух оболочек). Каждая фича ниже портируется **в единую оболочку**.

### Generator (`/app/generate`)
- [ ] Async-поллинг статуса генерации (legacy `GET /generate/status/{id}`)
- [ ] Персистентные «Недавние запуски» + endpoint истории (`GET .../recent`)
- [ ] Реальный cancel-endpoint
- [ ] Скачивание архива результата / архива регенерации
- [ ] Полная петля methodology-review (continue/edit/accept/compare, target picker, чат-ассистент)
- [ ] Scoped-регенерация endpoint
- [ ] 8-стадийный таймлайн, чекпойнт-состояние, score-ring, табы README/Practice/Data/Metrics/Report/Regeneration

### Checker / Аудитор (`/app/check`)
- [ ] Полная поверхность чекера, не «тонкий evaluator»
- [ ] Improvement-модалка (4-шаговый stepper, все поля)
- [ ] Improvement run-view (progress ring, timeline, таймер)
- [ ] Решить: improvement дергает generator/refine или checker-specific adapter
- [ ] Табы: Критерии 39 / Текст-статистика / Source README / Improved README

### Translator (`/app/translate`)
- [ ] Переключатель источника документ/видео
- [ ] Видео-режим: превью, upload-прогресс, output-тогглы (видео/субтитры/транскрипт), inline-загрузки
- [ ] Split-compare панели original/translated

### Curriculum / УП (`/up`)
- [ ] Иерархия страниц УП: список планов → деталь плана → row-edit → template proposals
- [ ] Row-edit экран (все поля строки УП)
- [ ] Template proposals (regenerate/accept/reject, правка полей)
- [ ] Связи «открыть бриф»
- [ ] Intake-воркспейс (бриф→каталог→DAG→УП): candidate-decisions, apply-catalog, build-DAG, export SVG/PNG/PDF

### Reference / Справочник (`/catalog-admin/*`, `/competencies`, `/profiles`, `/reviews`)

> Аудит из кода: reference уже покрывает 7 режимов (skills/competencies/profiles/reviews/
> candidates/templates/archive) + детали + CRUD. Audit-док был пессимистичен (писан до wiring).
> `groups` == `competencies` (service.groups проксирует). Реальные дыры — ниже.

- [x] **Reviews: фильтры severity/reason/entity** — backend (`/reference/reviews?severity&reason_code&entity_type`) + 3 селекта в panel + тесты (срез F2.1, готово)
- [x] catalog-admin: group-detail, skill-detail, candidate-competencies, artifact-templates, archive — уже были
- [x] Competencies список/деталь — уже было
- [x] Profiles (тоггл сервисных, дерево/деталь) — уже было
- [x] **Create-group** (`POST /reference/groups` = пустая competency-группа, без review, 409 на дубль) — срез F2.2, готово
- [x] **Reviews per-review confirm/ignore/return** — resolved/ignored/**open** (вернуть в очередь) через `PATCH /reference/reviews/{id}` — срез F2.3, готово
- [x] **apply-catalog / build-DAG** — НЕ отдельные кнопки: выполняются **автоматически** в intake-задаче (`POST /intake/jobs` пишет каталог + curriculum_plan; покрыто `test_intake_job_runs_pipeline_into_reference_and_curriculum`). Это выигрыш консолидации — ручные legacy-шаги слиты в один автоматический pipeline, не регресс.
- [ ] Left summary panel — есть в панели; финальный вид после D3 (s21-стиль)
- [~] **Skillsets** (`catalog_admin_skillsets*`) — **ОТЛОЖЕНО**. Решение владельца: зона другого
  методолога, назначение неясно. Проверено по коду: `skillset` имеет **0 использований** в
  пайплайне УП (и текущем, и legacy Spravochnik) — чисто viewer-admin сущность, не влияет на
  генерацию УП. Можно завести позже как отдельный слой, когда прояснится зачем.

### Dashboard / shell
- [ ] «Недавние запуски» с open/download/cancel + disabled-state
- [ ] Service-meta: статус, последний запуск, активные задачи
- [ ] Страница «Инструкция/Документация» как first-class маршрут (есть `app/static/instruction.html`)

## 4. Порядок работ (волны, каждая = зелёный приёмочный тест)

> Правило skill merge-and-refactor: малые обратимые срезы, тесты вперёд (характеризующие),
> 3 фейла подряд → стоп и пересмотр. Перед каждым изменением символа — GitNexus `impact`.
> Перед коммитом — `detect_changes({scope:"compare", base_ref:"main"})`.

| Волна | Содержание | Definition of Done |
|---|---|---|
| **F0. Развести доктрину** | D1–D4: переписать audit-док, починить копию дашборда, свести legacy-маршруты к единой оболочке, решить ярлык плитки | Нет упоминаний «второй оболочки»; дашборд-копия едина; маршруты Spravochnik рендерят единый shell; статик-тесты зелёные |
| **F1. Базовая приёмка** | Прогнать полный `pytest` + CI-гейты (`check_line_budget`, `check_grep_gates`, `check_duplicates`) на локальной PG; зафиксировать реальный red/green | Известен честный список падений; зелёный baseline или список багов в трекере |
| **F2. Reference parity** | Бэклог §3 Reference — портировать catalog-admin/competencies/profiles/reviews + summary-panel в единую панель | Каждая legacy-кнопка Справочника жива; парити-тест на панель + 1 e2e endpoint |
| **F3. Curriculum/УП parity** | Бэклог §3 Curriculum — иерархия УП, row-edit, template proposals, intake-воркспейс | УП создаётся/правится из БД; intake e2e зелёный; генератор тянет контекст из БД |
| **F4. Generator parity** | Бэклог §3 Generator — async-поллинг, recent runs, cancel, download, methodology-loop, регенерация | Генерация e2e на УП из БД; все кнопки формы/результата живые |
| **F5. Checker/Аудитор parity** | Бэклог §3 Checker — полная поверхность, improvement-модалка+run-view, обе оси в gate | «Битый» README ловится N.1–N.5; дидакт-профиль раздельно; improvement-флоу e2e |
| **F6. Translator parity** | Бэклог §3 Translator — видео-режим, output-тогглы, split-compare | doc+video перевод e2e; все кнопки живые |
| **F7. Финал** | Dashboard recent-runs + service-meta + Инструкция; убрать мёртвый код/дубли; пометить legacy archived | 5/5 плиток ведут в живые панели; каждая видимая кнопка = реальный вызов или детерминированный переход; legacy read-only |

## 5. Контракт приёмки (на каждую панель)

- Статик-тест: требуемые id/кнопки/табы существуют.
- JS/браузер-smoke: переходы (таб, экспандер, режим, выбор файла, loading/success/error).
- API-тест: каждый submit/action бьёт по реальному endpoint.
- GitNexus route/flow-check перед коммитом для изменённых UI/backend-маршрутов.
- Никаких мёртвых кнопок: контрол либо живой, либо скрыт до готовности backend.

## 6. Первые 3 шага (можно начинать сразу)

1. **F1 сначала** — прогнать полный `pytest` на локальной PG, чтобы знать реальную точку старта
   (план выше предполагает зелёный baseline; это надо подтвердить, а не верить).
2. **F0** — переписать `UI_LEGACY_PARITY_AUDIT.md` под единую доктрину + починить D2/D3/D4.
3. Завести трекер бэклога §3 (issues/чеклист) и идти волнами F2→F7, не начиная N+1 до зелёной N.
