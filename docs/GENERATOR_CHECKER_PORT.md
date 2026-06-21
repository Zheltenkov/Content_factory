# GENERATOR + CHECKER — разбивка на под-задачи (откалибровано под legacy ver1)

> Пути и строки — по фактическому `legacy/Content_generator` (ver1) в репо. Брать строго по одной,
> в порядке ниже. Перед каждой port-задачей — страж источника (остановит, если legacy не виден).
> Ориентир объёма — от ФАКТИЧЕСКОГО `wc -l` источника ver1 (числа ниже), не от целевого бюджета.

Реальность ver1: generator-логика = agents 13 367 + оркестрация content_gen/ ~9 000 ≈ **22k → бюджет 10k**
(компактизация ~45%, в основном за счёт свёртки 4 слоёв оркестрации). Checker validators **7 237**.
Примечание: `toc.py`, `skeleton.py`, `style_guard.py` в ver1 — заглушки по 9 строк; реальная логика
их функций в phase-executors / title_annotation / content_editor. Не жди от них кода.

---

# GENERATOR — настоящий порт

Порядок: G1 (спина) → G2 → G3 → G4a → G4b → G4c → G5.
**translator.py (1135) и translation_refiner.py (270) — НЕ сюда**, они в модуль translator.

### G1 — оркестрация → engine (первой)
Источник (`legacy/Content_generator/content_gen/`): orchestrator 412, phase_executors 271, flow_handlers 320,
node_services 779, node_contracts 180, node_executor_bundle 40, result_assembly 600, generation_runtime 130,
artifact_chain 299, domain_contracts 522, project_planning 355, project_seed_provider 250, workflow_profiles 160,
workflow_state 160, flow_result 45, context_phase_executor 318, exceptions 74 + agents/base/* + agents/flow.py 30.
(observability 787 -> в app/core/llm/observe; embeddings 90 -> core/llm или signals.) ~6.7k. Цель:
`app/modules/generator/{engine.py,service.py,domain.py}`. Ориентир ~1800–2000 (свернуть 4 слоя в 1).
```
ПОРТ оркестрации генератора (G1) в app/modules/generator/. ОДНА задача. Не брать следующую. Код ТОЛЬКО из источника.
ШАГ 0 — СТРАЖ: проверь legacy/Content_generator/content_gen/orchestrator.py не пуст; выведи `wc -l` всех
файлов источника (orchestrator, phase_executors, flow_handlers, node_services, node_contracts, result_assembly,
generation_runtime, artifact_chain, domain_contracts, project_planning, project_seed_provider, workflow_profiles,
workflow_state, context_phase_executor, agents/base/, agents/flow.py). Нет/пусто -> "LEGACY ОТСУТСТВУЕТ", СТОП.
ШАГ 1 — прочитай источник целиком; AGENTS.md; docs/CONSOLIDATION_PLAN.md (про «4 слоя -> engine.py»).
ШАГ 2 — СВЕРНИ оркестрацию в один engine.py (стадийный прогон + вызовы harness.augment/prepare/validate из
app/core/methodology); контракты -> domain.py; вход модуля -> service.py. observability -> app/core/llm/observe
(не дублируй). Базовый LLM-клиент НЕ дублируй — app/core/llm. Промпты -> app/core/llm/prompts/generator/.
ШАГ 3 — тест: engine прогоняет фиктивную стадию, зовёт harness, возвращает результат (реальное поведение).
ШАГ 4 — `wc -l` источника и engine.py; вывод теста; что свернул и почему.
DoD: engine реально оркеструет стадии и дергает harness; ≤2000 строк (свёртка ожидаема); тест зелёный. Не брать следующую.
```

### G2 — head: title / annotation / intro / planning
Источник: `agents/{title_annotation 517, intro_rules 724, context_analysis 30, intent_mapper 67, task_planner 292}.py`
+ `content_gen/structure_phase_executor.py 167`. (toc.py/skeleton.py — заглушки 9 строк, логика в title_annotation/structure_phase_executor.) ~1797. Цель: `app/modules/generator/stages/head.py`. Ориентир ~1000.
```
ПОРТ фазы head генератора (G2) в app/modules/generator/stages/head.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/title_annotation.py не пуст; `wc -l` (title_annotation, intro_rules,
context_analysis, intent_mapper, task_planner, content_gen/structure_phase_executor.py). Нет -> СТОП.
ШАГ 1 — прочитай источники; AGENTS.md. ШАГ 2 — перенеси РЕАЛЬНУЮ логику заголовка/аннотации/введения/планирования/
каркаса в head.py, вклинившись в engine из G1. Промпты -> prompts/generator/. ШАГ 3 — тест на реальное поведение
(H1+аннотация+TOC ожидаемой формы + граничный). ШАГ 4 — `wc -l`; тест; что не перенёс.
DoD: реальная логика head; тест зелёный; <40% от источника -> перечисли что и почему. Не брать следующую.
```

### G3 — theory
Источник: `agents/{theory 162, theory_completeness_agent 262, theory_enhancement_agent 76, theory_generation 179,
theory_generation_service 403, theory_materializer 55, theory_prompting 297, theory_sanitizer 268, definitions_agent 254,
length_agent 285, readability_agent 237}.py` + `content_gen/theory_phase_executor.py 568`. ~3046. Цель:
`app/modules/generator/stages/theory.py`. Ориентир ~1300.
```
ПОРТ фазы theory (G3) в app/modules/generator/stages/theory.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/theory_generation_service.py не пуст; `wc -l` всех theory_* (agents) +
content_gen/theory_phase_executor.py + definitions_agent, length_agent, readability_agent. Нет -> СТОП.
ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси генерацию теории (части, определения, длина/читабельность, санитайз);
theory_*-файлы дублированы — объедини без потери поведения. Промпты -> prompts/. ШАГ 3 — тест: N частей в норме +
граничный. ШАГ 4 — `wc -l`; тест; что слил. DoD: реальная генерация; тест зелёный; низкий % объясни (слияние дублей). Не брать следующую.
```

### G4a — practice core
Источник: `agents/{practice 416, practice_generation_service 258, practice_contracts 431, practice_materializer 253,
practice_parsing 129, practice_prompting 248, practice_finalizer 221}.py` + `content_gen/{practice_phase_executor 862,
practice_contract 209}.py`. ~3027. Цель: `app/modules/generator/stages/practice.py`. Ориентир ~1300.
```
ПОРТ practice-core (G4a) в app/modules/generator/stages/practice.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/practice_generation_service.py не пуст; `wc -l` (practice, practice_generation_service,
practice_contracts, practice_materializer, practice_parsing, practice_prompting, practice_finalizer,
content_gen/practice_phase_executor.py, content_gen/practice_contract.py). Нет -> СТОП.
ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси генерацию/контракты/материализацию/парсинг/финализацию заданий.
Критик/ремонт/бонус — НЕ здесь (G4b). Тяжёлые генераторы — НЕ здесь (G4c). Промпты -> prompts/.
ШАГ 3 — тест: N заданий с артефактами + граничный. ШАГ 4 — `wc -l`; тест; что отложено в G4b/G4c.
DoD: реальная генерация заданий; тест зелёный. Не брать следующую.
```

### G4b — practice critic / repair / bonus
Источник: `agents/{practice_critic 436, practice_repair 324, practice_bonus_service 221}.py`. ~981. Цель:
`app/modules/generator/stages/practice_review.py`. Ориентир ~600.
```
ПОРТ practice critic/repair/bonus (G4b) в app/modules/generator/stages/practice_review.py. ОДНА задача.
ШАГ 0 — СТРАЖ: legacy/.../agents/practice_critic.py не пуст; `wc -l` (practice_critic, practice_repair,
practice_bonus_service). Нет -> СТОП. ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси критику/ремонт/бонусы,
подключив к practice из G4a и inner-loop движка. ШАГ 3 — тест: критик ловит плохое задание, ремонт правит.
ШАГ 4 — `wc -l`; тест; что не перенёс. DoD: реальная логика; тест зелёный. Не брать следующую.
```

### G4c — тяжёлые генераторы: formula_table / dataset / code_example
Источник: `agents/{formula_table 1100, dataset_generator 620, code_example 271}.py`. ~1991. Цель:
`app/modules/generator/stages/generators.py`. Ориентир ~1200.
```
ПОРТ тяжёлых генераторов (G4c) в app/modules/generator/stages/generators.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/formula_table.py не пуст; `wc -l` (formula_table, dataset_generator, code_example).
Нет -> СТОП. ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси генерацию таблиц формул/датасетов/примеров кода;
детерминированные части (формулы) — кодом, не LLM. Промпты -> prompts/. ШАГ 3 — тест: каждый генератор -> валидный
артефакт + граничный. ШАГ 4 — `wc -l`; тест; что ужал. DoD: три генератора на реальной логике; тест зелёный;
formula_table 1100 — главный кандидат на сжатие, объясни как. Не брать следующую.
```

### G5 — refine: content_editor / quality_gate / enhancement / regeneration
Источник: `agents/{content_editor 607, quality_gate 303, enhancement_manager 430, enhancement_planner 603,
regeneration 814}.py` + `content_gen/regeneration_pipeline.py 305`. (style_guard.py — заглушка 9 строк, логика
стиля в content_editor / voice-скилле.) ~3062. Цель: `app/modules/generator/refine.py`. Ориентир ~1500.
```
ПОРТ фазы refine (G5) в app/modules/generator/refine.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../agents/content_editor.py не пуст; `wc -l` (content_editor, quality_gate,
enhancement_manager, enhancement_planner, regeneration, content_gen/regeneration_pipeline.py). Нет -> СТОП.
ШАГ 1 — прочитай; AGENTS.md. ШАГ 2 — перенеси пост-обработку (редактура, гейт качества, планирование/применение
улучшений, регенерацию по памяти отказов). ВАЖНО: quality_gate/стиль пересекаются с app/core/methodology (gate, voice) —
НЕ дублируй: где логика уже в core/methodology, вызывай её. ШАГ 3 — тест: refine улучшает черновик / триггерит
регенерацию. ШАГ 4 — `wc -l`; тест; что переиспользовал из core. DoD: реальная логика без дублей с methodology; тест зелёный. Не брать следующую.
```

---

# CHECKER — В ОСНОВНОМ НЕ ПОРТ (validators 7237 заменяются скиллами)

Старый `validators/rubric/*` (annotation 568, chapter1-3 2347, section1-4 1313, toc 759, scorer 279) — монолитный
структурный валидатор, который новая архитектура **заменяет** скиллами `readme_structure`+`document_integrity`
(собраны в волне M). Переносить целиком = дублировать скиллы. Поэтому типы под-задач разные.

### C1 — signals.py: консолидация эвристик (не 1:1 порт)
Донор логики: `validators/rubric/{similarity 259, document_utils 288, utils 230}.py` + детект из chapter/toc/annotation.
Цель: `app/modules/checker/signals.py` — ОДИН модуль эвристик (повторы/таблицы/диаграммы/похожесть) для обеих осей. ~500.
```
СОБЕРИ signals.py чекера (C1) в app/modules/checker/signals.py. ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../validators/rubric/similarity.py не пуст; `wc -l` (similarity, document_utils, utils). Нет -> СТОП.
ШАГ 1 — прочитай источники + docs/SKILLS_ARCHITECTURE.md (signals для обеих осей).
ШАГ 2 — КОНСОЛИДАЦИЯ, не копирование: вынеси переиспользуемые детекторы (похожесть/MOSS, повторы, таблицы,
диаграммы) в один signals.py с чистым API. НЕ тащи обвязку chapter/section — она в скиллах readme_structure/document_integrity.
ШАГ 3 — тест каждого детектора (чистый+битый). ШАГ 4 — `wc -l`; тест; что НЕ взял (дубли скиллов).
DoD: signals.py — единый источник эвристик, без дублей со скиллами; тест зелёный. Не брать следующую.
```

### C2 — структурная ось: ВАЙРИНГ скиллов (НЕ порт)
Источника для копирования нет — скиллы собраны. Цель: `app/modules/checker/structural.py` — прогон
`readme_structure`+`document_integrity` через harness, агрегация в `rubric_json`. ~250.
```
СОБЕРИ структурную ось (C2) в app/modules/checker/structural.py. НЕ ПОРТ — вайринг. ОДНА задача. Не брать следующую.
ЗАПРЕЩЕНО копировать validators/rubric — структурные проверки уже в скиллах readme_structure+document_integrity.
ШАГ 1 — прочитай app/core/methodology/harness.py + эти скиллы; docs/SKILLS_ARCHITECTURE.md §6.
ШАГ 2 — structural.py: на готовом README прогоняет скиллы через harness.validate(checker.evaluation), собирает
RuleIssue в rubric_json (формат для gate). Эвристики бери из signals.py (C1), не дублируй.
ШАГ 3 — тест: на эталонном «битом» README ось ловит дефекты и отдаёт rubric_json.
DoD: тонкий вайринг, 0 строк из rubric; тест зелёный. Не брать следующую.
```

### C3 — дидактическая ось: жюри (ГЕНЕРАЦИЯ ИЗ НОУТБУКА)
Источник: `docs/notebooks/didactic_quality_check_jury.ipynb`. Цель: `app/modules/checker/didactic/{jury.py,debate.py}`. ~800.
```
СОБЕРИ жюри (C3) в app/modules/checker/didactic/. НЕ ПОРТ из legacy — ГЕНЕРАЦИЯ из ноутбука. ОДНА задача. Не брать следующую.
ШАГ 1 — прочитай docs/notebooks/didactic_quality_check_jury.ipynb целиком; docs/DECISIONS.md D4; AGENTS.md.
ШАГ 2 — jury.py (PoLL: N вендор-разных моделей -> медиана, GENERATOR_MODEL исключён, abstain -> human_review) +
debate.py (critic/defender/judge на разных моделях). Слаги из конфига (D4, плейсхолдеры). LLM — через app/core/llm.
ШАГ 3 — тест на мок-LLM: медиана по 3 вердиктам; генератор не в жюри; abstain -> human_review. ШАГ 4 — вывод теста; что не реализовал.
DoD: медиана, исключение генератора, эскалация; тест зелёный. Не брать следующую.
```

### C4 — детерминированные проверки practice/theory (выборочный порт)
Источник: `validators/{practice_checks 349, theory_checks 160, practice 165, theory 76, structural_preflight 219,
structure 86}.py`. ~1055. Цель: недостающее -> в скиллы `checklist`/`content_sufficiency` ИЛИ `checker/service.py`. ~300.
```
ПОРТ детерминированных проверок practice/theory (C4). ОДНА задача. Не брать следующую.
ШАГ 0 — СТРАЖ: legacy/.../validators/practice_checks.py не пуст; `wc -l` (practice_checks, theory_checks, practice,
theory, structural_preflight, structure). Нет -> СТОП.
ШАГ 1 — прочитай источники; сверь с существующими скиллами checklist/content_sufficiency/readme_structure.
ШАГ 2 — перенеси ТОЛЬКО то, чего нет в скиллах. Что дублирует скилл — НЕ переноси, отметь в отчёте. Правило артефакта
-> в check.py скилла; оркестрация -> checker/service.py.
ШАГ 3 — тест (чистый+битый). ШАГ 4 — `wc -l`; тест; список того, что НЕ взял как дубль.
DoD: только недублирующее; тест зелёный. Не брать следующую.
```

---

## Сводка (ver1)
| Под-задача | Тип | Источник ver1 | строк | Цель | ориентир |
|---|---|---|---:|---|---:|
| G1 | порт (свёртка) | content_gen/ оркестрация | ~6700 | engine.py/domain.py | ~1900 |
| G2 | порт | title_annotation/intro_rules/… + structure_phase_executor | ~1797 | stages/head.py | ~1000 |
| G3 | порт (слияние) | theory_* + theory_phase_executor | ~3046 | stages/theory.py | ~1300 |
| G4a | порт | practice_* core + practice_phase_executor | ~3027 | stages/practice.py | ~1300 |
| G4b | порт | critic/repair/bonus | ~981 | stages/practice_review.py | ~600 |
| G4c | порт (сжатие) | formula_table/dataset/code_example | ~1991 | stages/generators.py | ~1200 |
| G5 | порт (без дублей core) | content_editor/quality_gate/enhancement/regeneration | ~3062 | refine.py | ~1500 |
| C1 | консолидация | rubric similarity/document_utils/utils | ~777 | signals.py | ~500 |
| C2 | вайринг (НЕ порт) | — (скиллы) | — | structural.py | ~250 |
| C3 | генерация из ноутбука | jury.ipynb | — | didactic/ | ~800 |
| C4 | выборочный порт | validators practice/theory/preflight | ~1055 | скиллы/service | ~300 |

Generator источник ~22k -> цель ~8800 (бюджет 10000) · Checker validators 7237 -> цель ~1850 (бюджет 3000).
Брать по одной, `wc -l` сверять глазами, не верить только зелёным тестам.

> Прочее в ver1, не в этом бэклоге: translator (agents/translator 1135 + translation_refiner 270 -> модуль translator);
> api/routers/* (curriculum 801, auth 591, admin 357, download 232 -> router.py модулей); api/db/* -> app/core/db + persistence;
> didactics/ (composer/loader -> композиция при генерации). Они в своих волнах TASKS.md.
