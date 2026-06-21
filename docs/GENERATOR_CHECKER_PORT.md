# GENERATOR + CHECKER — разбивка на под-задачи с готовыми промптами

> Два самых крупных модуля, где «одна задача» наиболее коварна. Брать строго по одной, в порядке ниже.
> Источник — `legacy/Content_generator/content_gen/`. Перед каждой port-задачей legacy обязан быть виден
> (страж источника в промпте остановит, если нет).

---

# GENERATOR — настоящий порт (источник ~20k → бюджет ≤10000)

Это реальный перенос. Оркестрация (~6.5k строк, 4 слоя) сворачивается в `engine.py`; агенты (13.6k,
сильно дублированы: theory_* в 8 файлов, practice_* в 12) переносятся по фазам с компактизацией.
**translator.py (841) и translation_refiner.py (272) — НЕ сюда**, они в модуль translator.

Порядок: G1 (спина) → G2 → G3 → G4a → G4b → G4c → G5. G2–G5 цепляются в engine из G1.

### G1 — оркестрация → engine (делать первым)
Источник: `content_gen/{orchestrator,phase_executors,context_phase_executor,flow_handlers,node_services,result_assembly,generation_runtime,artifact_chain,domain_contracts,project_planning,node_executor_bundle}.py` + `agents/{flow.py,base/}` (~6.5k). Цель: `app/modules/generator/{engine.py,service.py,domain.py}`. Ориентир: ~1500–2000 (свернуть 4 слоя в 1).
```
ПОРТ оркестрации генератора (G1) в app/modules/generator/. ОДНА задача. Не брать следующую.
Код ТОЛЬКО из прочитанного источника.
ШАГ 0 — СТРАЖ: проверь, что legacy/Content_generator/content_gen/orchestrator.py существует и не пуст;
выведи `wc -l` всех файлов источника (orchestrator, phase_executors, context_phase_executor, flow_handlers,
node_services, result_assembly, generation_runtime, artifact_chain, domain_contracts, project_planning,
agents/flow.py, agents/base/). Если нет/пусто -> "LEGACY ОТСУТСТВУЕТ — ПОРТ НЕВОЗМОЖЕН", СТОП.
ШАГ 1 — прочитай источник целиком; AGENTS.md; docs/CONSOLIDATION_PLAN.md (про «4 слоя -> engine.py»).
ШАГ 2 — СВЕРНИ 4 слоя оркестрации в один app/modules/generator/engine.py (стадийный прогон + вызовы
harness.augment/prepare/validate из app/core/methodology); контракты -> domain.py; вход модуля -> service.py.
Базовый LLM-клиент НЕ дублируй — используй app/core/llm. Промпты -> app/core/llm/prompts/generator/.
ШАГ 3 — тест: engine прогоняет фиктивную стадию, зовёт harness, возвращает результат (реальное поведение).
ШАГ 4 — `wc -l` источника и engine.py; вывод теста; что свернул/выкинул и почему (дубли слоёв — норм).
DoD: engine реально оркеструет стадии и дергает harness; ≤2000 строк (свёртка ожидаема); тест зелёный.
Не брать следующую задачу.
```

### G2 — head: title / annotation / toc / skeleton / intro
Источник: `agents/{title_annotation 492, toc 139, skeleton 208, intro_rules 716, context_analysis 30, intent_mapper 67, task_planner 290}.py` (~1942). Цель: `app/modules/generator/stages/head.py`. Ориентир ~1000.
```
ПОРТ фазы head генератора (G2) в app/modules/generator/stages/head.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: проверь legacy/Content_generator/content_gen/agents/title_annotation.py (не пуст), выведи
`wc -l` источников (title_annotation, toc, skeleton, intro_rules, context_analysis, intent_mapper,
task_planner). Нет/пусто -> "LEGACY ОТСУТСТВУЕТ", СТОП.
ШАГ 1 — прочитай источники; AGENTS.md; строку под generator в docs/TASKS.md.
ШАГ 2 — перенеси РЕАЛЬНУЮ логику генерации заголовка/аннотации/оглавления/каркаса/введения в head.py,
вклинившись в engine из G1. Промпты -> app/core/llm/prompts/generator/. Без дублей, функционал не терять.
ШАГ 3 — тест на реальное поведение: на входном брифе head выдаёт H1+аннотацию+TOC ожидаемой формы +
граничный кейс. ШАГ 4 — `wc -l` ист/результата; тест; что не перенёс и почему.
DoD: реальная логика head, тест зелёный, <40% от источника -> перечисли построчно что и почему. Не брать следующую.
```

### G3 — theory (теория, сильно дублирована)
Источник: `agents/{theory 162, theory_completeness_agent 254, theory_enhancement_agent 76, theory_generation 179, theory_generation_service 371, theory_materializer 55, theory_prompting 278, theory_sanitizer 270, definitions_agent 254, length_agent 285, readability_agent 237}.py` (~2421). Цель: `app/modules/generator/stages/theory.py`. Ориентир ~1200.
```
ПОРТ фазы theory генератора (G3) в app/modules/generator/stages/theory.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/theory_generation_service.py не пуст; `wc -l` всех theory_*, definitions_agent,
length_agent, readability_agent. Нет -> "LEGACY ОТСУТСТВУЕТ", СТОП.
ШАГ 1 — прочитай источники; AGENTS.md.
ШАГ 2 — перенеси логику генерации теории (части, определения, контроль длины/читабельности, санитайз) в
theory.py. ВАЖНО: 8+ theory_*-файлов сильно дублированы — объедини без потери поведения. Промпты -> prompts/.
ШАГ 3 — тест: theory выдаёт N частей в норме объёма + граничный (мало/много). ШАГ 4 — `wc -l`; тест; что слил.
DoD: реальная генерация теории; тест зелёный; низкий % -> объясни (слияние дублей theory_* — ожидаемо). Не брать следующую.
```

### G4a — practice core (генерация заданий)
Источник: `agents/{practice 416, practice_generation_service 249, practice_contracts 431, practice_contract(root) 209, practice_materializer 253, practice_parsing 129, practice_prompting 231, practice_finalizer 221, practice_phase_executor 887}.py` (~3026). Цель: `app/modules/generator/stages/practice.py`. Ориентир ~1300.
```
ПОРТ practice-core генератора (G4a) в app/modules/generator/stages/practice.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/practice_generation_service.py не пуст; `wc -l` источников
(practice, practice_generation_service, practice_contracts, practice_materializer, practice_parsing,
practice_prompting, practice_finalizer, practice_phase_executor, content_gen/practice_contract.py). Нет -> СТОП.
ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси генерацию/контракты/материализацию/парсинг/финализацию заданий
в practice.py. Критик/ремонт/бонусы — НЕ здесь (G4b). Тяжёлые генераторы данных — НЕ здесь (G4c). Промпты -> prompts/.
ШАГ 3 — тест: practice выдаёт N заданий с артефактами + граничный. ШАГ 4 — `wc -l`; тест; что отложено в G4b/G4c.
DoD: реальная генерация заданий; тест зелёный. Не брать следующую.
```

### G4b — practice critic / repair / bonus
Источник: `agents/{practice_critic 416, practice_repair 324, practice_bonus_service 212}.py` (~952). Цель: `app/modules/generator/stages/practice_review.py`. Ориентир ~600.
```
ПОРТ practice critic/repair/bonus (G4b) в app/modules/generator/stages/practice_review.py. ОДНА задача.
ШАГ 0 — СТРАЖ: legacy/.../agents/practice_critic.py не пуст; `wc -l` (practice_critic, practice_repair,
practice_bonus_service). Нет -> СТОП. ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси критику/ремонт/бонусные
задания, подключив к practice из G4a и inner-loop движка. ШАГ 3 — тест: критик ловит плохое задание, ремонт
правит (реальное поведение). ШАГ 4 — `wc -l`; тест; что не перенёс. DoD: реальная логика; тест зелёный. Не брать следующую.
```

### G4c — тяжёлые генераторы: formula_table / dataset / code_example
Источник: `agents/{formula_table 1100, dataset_generator 611, code_example 271}.py` (~1982). Цель: `app/modules/generator/stages/generators.py`. Ориентир ~1200.
```
ПОРТ тяжёлых генераторов (G4c) в app/modules/generator/stages/generators.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/formula_table.py не пуст; `wc -l` (formula_table, dataset_generator,
code_example). Нет -> СТОП. ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси генерацию таблиц формул / датасетов /
примеров кода для заданий; детерминированные части (формулы) — кодом, не LLM. Промпты -> prompts/.
ШАГ 3 — тест: каждый генератор выдаёт валидный артефакт + граничный кейс. ШАГ 4 — `wc -l`; тест; что ужал.
DoD: три генератора работают на реальной логике; тест зелёный. formula_table 1100 строк — главный кандидат
на компактизацию, объясни как ужал. Не брать следующую.
```

### G5 — refine: content_editor / style_guard / quality_gate / enhancement / regeneration
Источник: `agents/{content_editor 602, style_guard 374, quality_gate 303, enhancement_manager 430, enhancement_planner 596, regeneration 538}.py` (~2843). Цель: `app/modules/generator/refine.py`. Ориентир ~1500.
```
ПОРТ фазы refine генератора (G5) в app/modules/generator/refine.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/content_editor.py не пуст; `wc -l` (content_editor, style_guard, quality_gate,
enhancement_manager, enhancement_planner, regeneration). Нет -> СТОП. ШАГ 1 — прочитай; AGENTS.md.
ШАГ 2 — перенеси пост-обработку (редактура, стиль-гард, гейт качества, планирование/применение улучшений,
регенерацию по памяти отказов). style_guard/quality_gate частично пересекаются с методологическими скиллами
(voice, gate) — НЕ дублируй: где логика уже в app/core/methodology, вызывай её, а не переноси копию.
ШАГ 3 — тест: refine улучшает черновик / триггерит регенерацию (реальное поведение). ШАГ 4 — `wc -l`; тест;
что переиспользовал из core вместо переноса. DoD: реальная логика, без дублей с methodology; тест зелёный. Не брать следующую.
```

---

# CHECKER — В ОСНОВНОМ НЕ ПОРТ (внимание!)

**Ключевой нюанс.** Старый `validators/rubric/*` (6860 строк: chapter1/2/3, section1-4, annotation, toc,
scorer, similarity) — это МОНОЛИТНЫЙ структурный валидатор, который новая архитектура **заменяет**
методологическими скиллами (`readme_structure` + `document_integrity` — уже собраны в волне M). Переносить
rubric целиком = ДУБЛИРОВАТЬ скиллы, то есть ровно тот антипаттерн, против которого вся затея.

Поэтому checker — это смесь, и тип промпта разный по под-задаче:

### C1 — signals.py: собрать эвристики (консолидация из rubric, не 1:1 порт)
Источник (читать как донор логики, не копировать): `validators/rubric/{similarity 259, document_utils 85, utils 222}.py` + детект-логика из chapter/toc/annotation checkers. Цель: `app/modules/checker/signals.py` — ОДИН модуль эвристик (повторы/таблицы/диаграммы/похожесть), который кормит обе оси. Ориентир ~500.
```
СОБЕРИ signals.py чекера (C1) в app/modules/checker/signals.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/Content_generator/content_gen/validators/rubric/similarity.py не пуст; `wc -l`
(similarity, document_utils, utils). Нет -> СТОП.
ШАГ 1 — прочитай источники + docs/SKILLS_ARCHITECTURE.md (про signals, кормящий обе оси).
ШАГ 2 — это КОНСОЛИДАЦИЯ, не копирование: вынеси переиспользуемые детекторы (похожесть/MOSS, повторы,
таблицы, диаграммы) в ОДИН signals.py с чистым API. НЕ тащи проверочную обвязку chapter/section — она уже
в скиллах readme_structure/document_integrity. Только сырые сигналы.
ШАГ 3 — тест: каждый детектор на чистом+битом входе. ШАГ 4 — `wc -l` источников/результата; тест; что НЕ взял
(всё, что дублирует скиллы). DoD: signals.py — единый источник эвристик, без дублей со скиллами; тест зелёный. Не брать следующую.
```

### C2 — структурная ось: ВАЙРИНГ скиллов (НЕ порт)
Источника в legacy для копирования нет — скиллы уже собраны. Цель: `app/modules/checker/structural.py` — прогоняет `readme_structure` + `document_integrity` через harness на готовом артефакте, агрегирует в `rubric_json`. Ориентир ~250.
```
СОБЕРИ структурную ось чекера (C2) в app/modules/checker/structural.py. ОНА НЕ ПОРТ — вайринг.
ОДНА задача. Не брать следующую. ЗАПРЕЩЕНО копировать validators/rubric — структурные проверки уже
реализованы скиллами readme_structure + document_integrity.
ШАГ 1 — прочитай app/core/methodology/harness.py + скиллы readme_structure/document_integrity; docs/SKILLS_ARCHITECTURE.md §6.
ШАГ 2 — напиши structural.py: на готовом README прогоняет эти скиллы через harness.validate(checker.evaluation),
собирает RuleIssue в rubric_json (формат, который читает gate). Используй signals.py из C1, не дублируй эвристики.
ШАГ 3 — тест: на эталонном «битом» README структурная ось ловит дефекты и отдаёт rubric_json.
DoD: ось = тонкий вайринг скиллов, 0 строк скопированы из rubric; тест зелёный. Не брать следующую.
```

### C3 — дидактическая ось: жюри (ГЕНЕРАЦИЯ ИЗ НОУТБУКА, не порт)
Источник: `docs/notebooks/didactic_quality_check_jury.ipynb` (PoLL: ≥3 модели -> медиана, генератор исключён,
debate critic/defender/judge, abstain -> human). Цель: `app/modules/checker/didactic/{jury.py,debate.py}`. Ориентир ~800.
```
СОБЕРИ дидактическое жюри (C3) в app/modules/checker/didactic/. ОНА НЕ ПОРТ из legacy — ГЕНЕРАЦИЯ из ноутбука.
ОДНА задача. Не брать следующую.
ШАГ 1 — прочитай docs/notebooks/didactic_quality_check_jury.ipynb целиком; docs/DECISIONS.md D4 (правило жюри);
AGENTS.md.
ШАГ 2 — реализуй jury.py (PoLL: N вендор-разных моделей -> медиана, GENERATOR_MODEL исключён, abstain при
низкой уверенности -> human_review) и debate.py (critic/defender/judge на разных моделях). Слаги моделей — из
конфига (DECISIONS D4, пока плейсхолдеры). LLM — через app/core/llm.
ШАГ 3 — тест на мок-LLM: медиана по 3 вердиктам; генератор не в жюри; abstain -> human_review (реальное поведение).
ШАГ 4 — вывод теста; какие места ноутбука не реализовал и почему.
DoD: жюри считает медиану, исключает генератор, эскалирует; тест на мок-моделях зелёный. Не брать следующую.
```

### C4 — детерминированные проверки practice/theory (выборочный порт)
Источник: `validators/{practice_checks 349, theory_checks 160, practice 142, theory 77}.py` (~728). Цель: добавить недостающее в `checklist`/`content_sufficiency` скиллы ИЛИ в `checker/service.py`. Ориентир ~300.
```
ПОРТ детерминированных проверок practice/theory (C4). ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../validators/practice_checks.py не пуст; `wc -l` (practice_checks, theory_checks,
practice, theory). Нет -> СТОП.
ШАГ 1 — прочитай источники; сверь с уже существующими скиллами checklist/content_sufficiency.
ШАГ 2 — перенеси ТОЛЬКО то, чего ещё нет в скиллах (объективные проверки заданий/теории). Что дублирует
скилл — НЕ переноси, отметь в отчёте. Куда класть: если это правило артефакта -> в соответствующий скилл
check.py; если оркестрация -> checker/service.py.
ШАГ 3 — тест на чистом+битом. ШАГ 4 — `wc -l`; тест; список того, что НЕ взял как дубль скилла.
DoD: перенесено только недублирующее; тест зелёный. Не брать следующую.
```

---

## Сводка
| Под-задача | Тип | Источник | Цель | ориентир |
|---|---|---|---|---|
| G1 | порт (свёртка) | orchestration ~6.5k | engine.py | ~1800 |
| G2 | порт | head agents ~1.9k | stages/head.py | ~1000 |
| G3 | порт (слияние дублей) | theory_* ~2.4k | stages/theory.py | ~1200 |
| G4a | порт | practice core ~3k | stages/practice.py | ~1300 |
| G4b | порт | critic/repair/bonus ~0.95k | stages/practice_review.py | ~600 |
| G4c | порт (компактизация) | formula/dataset/code ~2k | stages/generators.py | ~1200 |
| G5 | порт (без дублей core) | refine ~2.8k | refine.py | ~1500 |
| C1 | консолидация | rubric similarity/utils | signals.py | ~500 |
| C2 | вайринг (НЕ порт) | — (скиллы) | structural.py | ~250 |
| C3 | генерация из ноутбука | jury.ipynb | didactic/ | ~800 |
| C4 | выборочный порт | practice/theory_checks | скиллы/service | ~300 |

Generator ≈ ~8600 (бюджет 10000) · Checker ≈ ~1850 (бюджет 3000). Брать строго по одной, сверять `wc -l`
своими глазами, не верить только зелёным тестам.
