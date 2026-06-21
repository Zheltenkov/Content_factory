# SKILLS_ARCHITECTURE.md — слой методических правил (skills / hooks / harness / profiles)

> Спутник `CONSOLIDATION_PLAN.md`. Описывает, как организовать правила генерации так, чтобы
> добавление направления (Дети, Коммерция, …) было `profile.yaml` + папки-оверрайды, а не форком.
> Все скиллы и оверрайды ниже выведены из трёх регламентов (Основа / Дети / Коммерция, Раздел III)
> и сверены с текущей реализацией `content_gen/didactics/`.
>
> **Ревизия v2** (по архитектурному ревью): namespaced-стадии `<consumer>.<stage>`; разведение
> methodology skill ↔ educational competency; таксономия program_type / artifact_target / content_model;
> две модели Дети вместо одной плоской `lesson`; `produces`/`requires` для producer-скиллов;
> библиотека в `core/methodology/profiles`; `document_integrity` выделен из `readme_structure`.

---

## 0. Что чиним (текущее состояние, факт из кода)

- **Два конкурирующих манифеста:** `didactics/manifest.yaml` (v1.0.0, ссылается на несуществующие файлы) и `content_gen/didactics/manifest.yaml` (v1.1.0, `skill_specs` + `agent_bindings`).
- **`machine_rules: []` всегда пуст** — `composer.py` собирает только `file`; severity `hard` декоративный, исполняемое принуждение оторвано в `validators/rubric/` (~5k строк, дублируют `readme_strcture.json`).
- **Одно направление зашито** (`bundle_id: "school21_readme_ru"`), один `readme_strcture.json` (3 главы). Регламенты требуют: Основа — Введение / Теория / **Инструкция отдельно** / Tasks+Exercises / **Приложения**; Коммерция — **две версии** (линейная + циклическая); Дети — **другую контент-модель** (занятия, не README).

Фундамент (skill=markdown + binding + severity) правильный — достраиваем, не выбрасываем.

---

## 1. Два слоя — граница, которую нельзя стирать

| | Слой ПРАВИЛ (этот спек) | Слой РЕШАТЕЛЯ (`engine.py`) |
|---|---|---|
| Отвечает на | **ЧТО** — какие ограничения, где, насколько жёстки | **КАК** — как агент сходится к результату и чинит провалы |
| Форма | декларативный (yaml + md + опц. check.py) | императивный (петли, диспетчинг, регенерация) |
| Содержит | skill / hook-биндинги / profile | inner/outer loop, jury, on.repair, failure-memory |
| Правило | **скилл — это спека** | **движок — это решатель** |

**Запрет:** не класть control-flow внутрь скилла. Скилл декларирует правило и (опц.) проверку; *как* агент к нему сходится — дело движка. Иначе знание намертво сцепляется с управлением, и нельзя сменить стратегию вывода, не трогая правила. Контур исполнения вынесен в §7 именно чтобы эта граница была видна.

---

## 2. Базовые понятия

- **Skill** — единица методического знания. Самодостаточная папка: манифест + проза для LLM + опц. исполняемое правило. Паттерн Anthropic `SKILL.md`.
- **Hook** — именованная точка перехвата в пайплайне (глагол жизненного цикла). Хук = интерфейс, скилл = реализация, втыкаемая в него.
- **Harness** — рантайм правил: грузит профиль → разворачивает эффективный набор скиллов → привязывает по хукам к стадиям → на каждой стадии файрит хук. Тонкий слой над `engine.py`, заменяет хардкод `agent_bindings`.
- **Profile** — направление как слой. `_base` (Основа) + оверлеи (Дети/Коммерция), наследование и точечное переопределение (как CSS-каскад / Kustomize).

> **Терминологический разнобой, который нельзя допустить.** Слово «skill» перегружено:
> - **methodology skill** (в этом спеке — просто «скилл») — единица методического *правила*: prompt-инструкция, детерминированная проверка, repair-hint или контракт артефакта.
> - **competency** (образовательный навык из Справочника) — то, что регламент в 3.1.2 называет «skills»: навык студента, с весом %, индикаторами, траекторией. В коде/БД/API это `competency_*` (как уже сделано в Spravochnik: `competency_catalog`, `competency_profile`) — **никогда не `skill`**.
>
> Поэтому скилл, раздающий веса навыкам, называется `competency_weights`, а не `skill_weights`: он *оперирует* competency, а сам *является* methodology skill.

### 2.1 Таксономия артефактов (четыре различимых оси)

Каждая отвечает на свой вопрос — не смешивать:

| Ось | Вопрос | Значения | Где живёт |
|---|---|---|---|
| **program_type** | какой *продуктовый формат* | основная / интенсив / мастер-класс | поле профиля; выбирает target + params |
| **artifact_target** | какой *документ* генерим сейчас | curriculum_plan / readme_project / teacher_guide / presentation / checklist | задаётся запуском |
| **content_model** | по какому *структурному шаблону* | readme_linear / readme_cyclic / lesson_course / lesson_single / … | **свойство artifact_target, НЕ профиля** |
| **artifact_family** | грубый *тег применимости* | readme / lesson / guide / slides | тег на content_model — для cross-cutting скиллов |

**Правило разведения `content_model`:** новый content_model создаётся ⟺ различается набор **обязательных разделов верхнего уровня** (`check.py` ветвится на присутствие/отсутствие целых блоков). Если различаются пороги, счётчики, состав тестов, длительность — это `params`. Тест на запах: `if program_type==X: skip шесть разделов` → другая модель; `if program_type==X: threshold=Y` → параметр.

**content_model — на artifact_target, не на профиль.** Одна программа Дети выпускает несколько артефактов (план + методички наставника + презентации), у каждого свой content_model. Поэтому профиль не несёт один глобальный `content_model`.

---

## 3. Анатомия скилла

```
skills/<id>/
├── skill.yaml          # манифест: хуки, стадии, severity, параметры
├── instructions.md     # проза → в промпт (для LLM). Опускается, если скилл чисто машинный
└── check.py            # ОПЦ. исполняемое правило (для гейта). Опускается, если скилл чисто промптовый
```

### 3.1 `skill.yaml`

```yaml
id: visual_quality
title: Качество визуальных материалов
source: "Регламент 3.2.5"            # трассируемость к регламенту
hooks:
  - at: prompt.augment               # вклеить instructions в промпт этих стадий
    stages: [generator.theory, generator.practice]   # стадии namespaced: <consumer>.<stage>
  - at: post.validate                # прогнать check.py после этих стадий
    stages: [generator.evaluation]
severity: hard                       # hard → critical issue (блокирует/в гейт); soft → warning
params:                              # параметры скилла — переопределяемые профилем
  min_resolution: [1200, 800]
  min_dpi: 96
  max_file_kb: 1024
  formats: [png, jpg, svg]
instructions: instructions.md        # путь относительно папки скилла (опц.)
check: check.py                      # путь (опц.); если нет — скилл только промптовый
```

**Скилл-продюсер (planner-стадия) объявляет поток данных** — чтобы planner писал контекст, а downstream только читал, без повторного исполнения:

```yaml
id: competency_weights
title: Развесовка компетенций в УП
source: "Регламент 3.1.2"
hooks:
  - at: pre.stage
    stages: [curriculum.planner]      # исполняется ТОЛЬКО в curriculum (по стадии)
requires: [reference.competencies, curriculum.projects]   # что читает из контекста
produces: [curriculum.competency_weights]                 # что пишет в контекст
params: {weight_total: 100}
check: check.py                       # сумма весов == 100, навык существует в Справочнике
```

`generator` затем *читает* `curriculum.competency_weights` из `CurriculumContext` как данные — не запускает скилл повторно. `requires`/`produces` опциональны, нужны только там, где есть поток данных между потребителями; они делают контракт тестируемым: продюсер не висит на `generator.*`, и никто не требует ключ, который никто не производит. (`consumed_by` сознательно НЕ вводим — это зацепление в обратную сторону; потребитель сам объявляет `requires`.)

### 3.2 `instructions.md` — контракт

Чистая проза правил для модели. Без условной логики, без шаблонов под Jinja. Параметры подставляются harness'ом из `params` через простую замену `{{param}}` — чтобы один и тот же текст работал на всех направлениях с разными числами.

### 3.3 `check.py` — контракт

Ровно одна функция. Без сети, без LLM, детерминированно. Возвращает список нарушений в форме, которую потребляет `MethodologyGate`:

```python
# core/methodology/rules.py
@dataclass
class RuleIssue:
    skill_id: str
    code: str                 # "visual_quality.low_resolution"
    severity: str             # "hard" | "soft"
    message: str
    evidence: dict = field(default_factory=dict)

# skills/visual_quality/check.py
def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    issues = []
    for img in doc.images:
        if img.width < params["min_resolution"][0] or img.height < params["min_resolution"][1]:
            issues.append(RuleIssue("visual_quality", "visual_quality.low_resolution",
                "hard", f"{img.path}: {img.width}×{img.height} < {params['min_resolution']}"))
    return issues
```

`check.py` скиллов с `post.validate` → агрегируются harness'ом в `rubric_json` (структурная ось плана). Сюда переезжают проверки из `structural_criteria_v2`, но **по разным скиллам**: PREFLIGHT (P.1–P.6) и каркас — в `readme_structure`; кросс-документная целостность (N.1–N.5: таблицы, повторы, кавычки, диаграмма↔тема, project-id) — в отдельный скилл `document_integrity` (применим ко всем content_model, включая `lesson_*`). **Это и есть возвращённые к жизни `machine_rules`** — вместо одного 5k-строчного императивного модуля.

---

## 4. Хуки — контракт

Минимальный набор. Больше не добавлять без необходимости.

| Хук | Сигнатура | Когда файрится | Назначение |
|---|---|---|---|
| `prompt.augment` | `(stage, ctx) -> str` | перед вызовом LLM на стадии | вернуть текст инструкций для вклейки в промпт |
| `pre.stage` | `(stage, ctx) -> ctx'` | до стадии, детерминированно | политика/подготовка: развесовка компетенций, MediaPlan, workload, секвенирование |
| `post.validate` | `(stage, doc, ctx) -> [RuleIssue]` | после стадии | машинная проверка → issues в гейт (структурная ось) |
| `on.repair` | `(issue, ctx) -> str` | в inner-loop при провале | вернуть точечную инструкцию ремонта (опц.; иначе берётся `issue.message`) |

**Стадии — namespaced: `<consumer>.<stage>`.** Это делает маршрутизацию железной (хук + стадия = точка исполнения), а не договорённостью «planner — это curriculum». `evaluation` есть у генератора, чекера, curriculum и будущего exam-модуля — без namespace через полгода ambiguity.

- `curriculum.planner`, `curriculum.plan` — планировщик / валидация УП
- `generator.title_annotation`, `generator.intro`, `generator.theory`, `generator.practice`, `generator.content_editor`, `generator.style_guard`, `generator.evaluation`
- `checker.evaluation` — финальная проверка готового артефакта

Скилл объявляет свои стадии в `skill.yaml.hooks[].stages`; список стадий и есть контракт «кто меня исполняет». `competency_weights` со `stages: [curriculum.planner]` физически не может выстрелить в генераторе.

> **Ключ хука — `at`, не `on`.** YAML 1.1 (PyYAML по умолчанию) приводит голый `on:` к булеву `True` (та же «Norway problem», что у GitHub Actions). Поэтому каждый хук-элемент пишется `- at: <hook>` / `stages: [...]`, без кавычек-костылей.

---

## 5. Профили — слоистая композиция

### 5.1 `profile.yaml`

```yaml
# kids/profile.yaml
id: kids
title: Детское направление (Старт)
extends: _base
terminology:                          # словарь направления
  branch: программа
  curriculum: программа обучения
overrides: [voice, checklist]         # заменить скилл целиком (своей папкой)
disables: [readme_structure]          # README-каркас не применим (у Дети — модели lesson_*)
adds: [program_types, lesson_structure, mentor_assets, assessments, student_portrait]

# program_type выбирает artifact_target + content_model + params. НЕ три модели на каждый тип:
# основная и интенсив структурно идентичны (lesson_course), различаются params; мастер-класс —
# другой набор top-level разделов (lesson_single).
program_types:
  main:         {artifact_target: curriculum_plan, content_model: lesson_course,
                 params: {assessments: [entry, midterm, final], lesson_hours: [2,4], project_span: [2,4]}}
  intensive:    {artifact_target: curriculum_plan, content_model: lesson_course,
                 params: {assessments: [final],                 lesson_hours: [4],   project_span: [2,5]}}
  master_class: {artifact_target: curriculum_plan, content_model: lesson_single,
                 params: {duration_minutes: 90}}

params:                               # точечная правка существующих скиллов БЕЗ замены
  audience_level.min_age: 7
  content_sufficiency.words_per_part: [80, 180]   # легче, чем в Основе
  voice.formality: warm_mentor
assets:                               # неизменные блоки именно этого направления
  template_blocks: kids/assets/blocks/
```

### 5.2 Алгоритм резолвинга (harness)

```
1. profile = load(id); chain = [profile, ...resolve(profile.extends)]   # kids → _base
2. skills = union(base.skills) for base in reversed(chain)              # базовые
3. skills -= disables                                                   # выключить
4. skills = (skills − overrides_ids) ∪ overrides_folders                # заменить
5. skills += adds                                                       # добавить
6. for k,v in profile.params: set(skills[skill].params[key], v)         # точечные параметры
7. program_type → artifact_target + content_model + params; terminology + assets → в контекст
=> effective_profile: плоский список скиллов с финальными params
```

`content_model` — свойство **artifact_target**, не профиля: для `readme_project` это `readme_linear` (Основа) или `readme_cyclic` (Коммерция, через `params`); для `curriculum_plan` Дети — `lesson_course` (основная/интенсив) или `lesson_single` (мастер-класс). Это снимает зашитость `readme_strcture.json`: структура — данные, выбираемые под конкретный артефакт.

---

## 6. Harness — резолвинг + диспетчинг

```python
# core/methodology/harness.py  (~150 строк всего)
profile = resolve_profile(direction_id)              # §5.2
bind = index(profile.skills, by=("hook", "stage"))   # {(hook,stage): [skill...]}

# движок дёргает на каждой стадии:
def augment(stage, ctx):
    return "\n\n".join(render(s.instructions, s.params)
                       for s in bind[("prompt.augment", stage)])

def prepare(stage, ctx):
    for s in bind[("pre.stage", stage)]: ctx = s.pre(stage, ctx)
    return ctx

def validate(stage, doc, ctx):
    return [i for s in bind[("post.validate", stage)] for i in s.check(doc, s.params)]
```

`augment`/`prepare` зовутся вокруг каждой стадии; `validate` — в `generator.evaluation` и `checker.evaluation` (и опц. после каждой стадии для inner-loop, §7). Issues едут в `MethodologyGate._review_evaluation` как `rubric_json`.

### 6.1 Где живёт библиотека и куда смотрят зависимости

У библиотеки скиллов **два потребителя** (curriculum и generator), поэтому она живёт в ядре, а не в модуле:

```
core/methodology/
├── harness.py          # диспетчер хуков — общий
├── rules.py            # контракт: RuleIssue, GeneratedDoc, MethodologyContext, ArtifactRef
└── profiles/           # БИБЛИОТЕКА СКИЛЛОВ (данные)
    ├── _base/skills/
    ├── kids/skills/
    └── commerce/skills/

modules/curriculum/     # fire("pre.stage","curriculum.planner") / ("post.validate","curriculum.plan")
modules/generator/      # fire("prompt.augment","generator.theory") / ("post.validate","generator.evaluation")
modules/checker/        # fire("post.validate","checker.evaluation")
```

**Зависимость строго `core ← {curriculum, generator, checker}`.** `core/methodology` НЕ импортирует модули — знает только абстракции (`GeneratedDoc`, `RuleIssue`, `MethodologyContext`, `ArtifactRef`). Модули сами адаптируют свои данные: `CurriculumPlan → MethodologyContext`, `GenerationResult → GeneratedDoc`. Иначе ядро тихо станет монолитом.

### 6.2 Producer/consumer — один скилл не исполняется дважды

`competency_weights` и `branch_structure` — planner-стадийные: исполняются на `curriculum.planner`, пишут результат в контекст УП (`produces`), а генератор его **читает** (через `CurriculumContext`), не пересчитывая. Это не повторный запуск скилла, а потребление данных. `produces`/`requires` (§3.1) фиксируют этот поток и делают его тестируемым: CI проверяет, что producer-скилл не привязан к `generator.*` и что каждый `requires` кем-то производится.

---

## 7. Контур исполнения (СЛОЙ РЕШАТЕЛЯ — не правила)

Из «модных» агентных паттернов берём ровно два; остальное либо уже в системе, либо сознательно за бортом.

### 7.1 Двухуровневая петля рефлексии

Следует *автоматически* из раздельности двух осей — не отдельная фича, а следствие архитектуры.

- **Inner loop — дёшево, детерминированно, на каждой стадии.** После стадии → `post.validate` (структурная ось). HARD-провал машинного правила (битая таблица, нет якоря, картинка <1200×800, не тот объём) → агент чинит **в той же стадии**, получив конкретное нарушение как фидбек. Без LLM-судьи, без полной регенерации. `on.repair` даёт точечную подсказку. **Лимит 1–2 итерации, потом стоп.**
- **Outer loop — дорого, субъективно, один раз на финализации.** Дидактическое жюри (PoLL: N моделей → медиана, генератор исключён, эскалация critic/defender/judge, отказ при низкой уверенности). Стоит несколько моделей → запускается единожды в конце. Провал/отказ → регенерация или человек.

Соответствие: **структурная ось = дешёвый внутренний self-repair; дидактическая ось = дорогая внешняя рефлексия.** Не гонять outer там, где справляется inner.

### 7.2 Память отказов (Reflexion, буквально)

Регенерация не должна быть безпамятной. По документу копится структурированная история попыток (что упало, почему, что меняли) и подаётся в следующую попытку → не повторяет те же ошибки. Дешёвый эпизодический буфер (список dataclass'ов в состоянии запроса), **не** векторная БД.

### 7.3 Что уже есть (не путать с пробелами)

| Паттерн | Где живёт |
|---|---|
| Reflection / Reflexion | петля `gate → регенерация` + `on.repair` |
| LLM-as-judge + debate + self-consistency | дидактическое жюри (§ checker в плане) |
| Plan-and-Execute | сам пайплайн УП → стадии |
| Router / cascade | эскалация жюри на спорных дименшенах |

### 7.4 ReAct — сознательно за бортом

ReAct даёт модели агентность *в середине* задачи (думать→инструмент→наблюдать). Для учебного контента это ровно то, что убирали: сквозной принцип «факты — ИИ, решения — правила/люди», контекст выносится вверх (УП из БД), валидация вниз (гейт), генерация остаётся ограниченным трансформом. ReAct вернул бы недетерминизм в середину → рушит аудируемость. Узкое исключение — дёрнуть Справочник на лету, чего нет в предсобранном контексте; даже это лучше решать предзагрузкой.

### 7.5 Дисциплина (НЕ делать)

- Не дебатить структурную ось — сломанная таблица не нуждается в трёх моделях.
- Не рефлексировать над рефлексией — inner 1–2 итерации, outer один проход, дальше человек.
- Не класть control-flow в скиллы (см. §1).

---

## 8. Каталог скиллов: регламент → скилл → хук → severity

`A` = prompt.augment, `P` = pre.stage, `V` = post.validate, `R` = on.repair. Стадии в таблице — сокращение namespaced-формы: `planner`=`curriculum.planner`, `evaluation`=`generator.evaluation` (+ `checker.evaluation` где указано), `gen·*`=`generator.*`.

### 8.1 Базовые (`_base`, направление Основа)

| Скилл | Регл. | Хуки (стадии) | Sev | check.py (машинное правило) |
|---|---|---|---|---|
| `voice` | 3.2.4 | A(gen·*), V(style_guard) | soft | детект канцелярита/болванок (опц.) |
| `readme_structure` | 3.2.3 | A(gen·*), V(evaluation) | hard | PREFLIGHT P.1–6 + каркас по `content_model` (см. эталон) |
| `document_integrity` | structural_criteria_v2 | V(evaluation, checker.evaluation) | hard | N.1–5: целостность таблиц, дословные повторы, кавычки, диаграмма↔тема, единый project-id; на всех content_model / artifact_family |
| `content_sufficiency` | 3.2.2 | A(theory,practice) | soft | — (кормит дидактический scaffolding) |
| `branch_structure` | 3.2.1 | P(planner) | soft | лестница простое→сложное, преемственность; produces порядок |
| `audience_level` | 3.1.1 | P(planner) | soft | ~30% с опытом, ветка-из-ветки |
| `competency_weights` | 3.1.2 | P(planner) | soft | сумма весов=100; навык есть в Справочнике; produces `curriculum.competency_weights` |
| `software_constraints` | 3.1.2 | A(intro), V(evaluation) | soft→hard | РФ-доступность, офиц. каналы, без пиратства |
| `visual_quality` | 3.2.5 | A(theory,practice), V(evaluation) | hard | разрешение ≥1200×800, DPI ≥96, формат, вес ≤1МБ |
| `checklist` | 3.3 | A(practice), V(evaluation) | hard | yml-формат; объективность («выполнено/нет»), детект расплывчатых формулировок |
| `repository_structure` | 3.5 | V(evaluation) | hard | типовые директории; `tests/`+`check-list.yml` НЕ в for_forks |
| `autotests` | 3.7 | P(planner) | soft | техническое→required; теоретическое→чек-лист; языки Docker (C/C++,Python,SQL) |
| `template_blocks` | 3.2.3 | A(verbatim), V(evaluation) | hard | присутствие+неизменность блоков (правила/дисклеймер/обр.связь); ассеты профиля |
| `workload_planning` | 3.1.3 | P(planner) | soft | `Y=X·0.34+3`; 3 проверки (мин 2); p2p кратно 15 мин |
| `access_constructors` | 3.1.2 | P(planner) | soft | последовательно/после-ревью/параллельно + факторы |

### 8.2 Дети (`kids`) — оверлей

| Действие | Скилл | Регл. | Примечание |
|---|---|---|---|
| override | `voice` | 3.2.4 | упрощение терминов + обяз. проф. название; `formality: warm_mentor` |
| override | `checklist` | 3.3 | обяз. пункты: роли, командная работа, коммуникация |
| param | `audience_level` | 3.1.1 | `min_age`, входная диагностика |
| disable | `readme_structure` | — | README-каркас не применим (модели `lesson_*`) |
| **add** | `program_types` | 3.1.3 | основная+интенсив → `lesson_course` (различие в params); мастер-класс → `lesson_single` |
| **add** | `lesson_structure` | 3.1.3 | занятия 2–4 ак.ч; проект = 2–4 (осн.) / 2–5 (интенсив) занятий |
| **add** | `mentor_assets` | 3.1.3 | презентация + методичка наставника; портрет наставника |
| **add** | `assessments` | 3.1.3 | состав по program_type: осн.=[entry,midterm,final], интенсив=[final] |
| **add** | `student_portrait` | 3.1.3 | ЗУН + софт-скиллы на выходе; SJM (нет в `lesson_single`) |

### 8.3 Коммерция (`commerce`) — оверлей

| Действие | Скилл | Регл. | Примечание |
|---|---|---|---|
| param | `readme_structure.content_model` | 3.2.3 | `readme_cyclic` — циклическая теория→практика (ОДИН параметр, не подмена папки) |
| param | `content_sufficiency` | 3.2.3 | теория подробнее (не-программирование / новички — не должны догадываться) |
| param | `voice` | 3.2.3 | тон под более развёрнутую теорию |
| override | `template_blocks` | 3.2.3 | иная подача обратной связи (всплывашка платформы); инструкция выносится ссылкой |
| param | `readme_structure.naming` | 3.2.3 | нейминг «не по файлу нейминга» |

---

## 9. Миграция с текущего состояния

| Сейчас | Становится |
|---|---|
| `didactics/manifest.yaml` + `content_gen/didactics/manifest.yaml` (два) | `_base/profile.yaml` + `_base/skills/*/skill.yaml` (один источник) |
| `skill_specs[].file` (только проза) | `skills/<id>/instructions.md` |
| `skill_specs[].machine_rules: []` (мертво) | `skills/<id>/check.py` (живое, в гейт) |
| `agent_bindings: {agent: [ids]}` | `skill.yaml.hooks[].stages` (биндинг на стороне скилла, namespaced) |
| `validators/rubric/*` (~5k, императив) | `readme_structure/check.py` + `document_integrity/check.py` + точечные (~700 суммарно) |
| `patterns.py` (зашитые регэкспы) | внутрь `readme_structure/check.py` нужного `content_model` |
| `bundle_id: "school21_readme_ru"` | профили `_base` / `kids` / `commerce` в `core/methodology/profiles` |
| `threshold_refs` | `skill.yaml.params` (+ общий `core/config/thresholds.yaml` как дефолты) |

`composer.compose_didactics_context(agent)` → `harness.augment(stage, ctx)`. Контракт трассировки (`didactics_skills_used`, версии) сохраняется — расширяется полем активного профиля и program_type.

---

## 10. Пробелы регламента, закрываемые попутно

Выявлены при разборе Основы (детально — в обсуждении). Учесть при генерации скиллов:

1. **Веса компетенций (%)** (3.1.2) — `CurriculumContext.current_project_skills` сейчас `list[str]` без весов; вес приходит из компетентностного профиля Справочника → скилл `competency_weights` на `curriculum.planner` (produces в контекст, generator читает).
2. **Инструкция отдельной главой + Приложения** (3.2.3) — текущий json склеивает Введение+Инструкцию и не имеет Приложений → в каркасе `readme_linear`.
3. **Циклическая структура** (Коммерция 3.2.3) — не моделируется, структурный чекер зарежет → `content_model: readme_cyclic` (через `params`).
4. **Визуальные требования как машинные** (3.2.5) — сейчас проза → `visual_quality/check.py`.
5. **Неизменные шаблонные блоки per-направление** (3.2.3) → `template_blocks` (ассеты профиля + проверка неизменности).
6. **Дети — другая контент-модель** (3.1.3) — не tone-оверрайд, а две модели (`lesson_course` для основной/интенсива, `lesson_single` для мастер-класса) + 5 новых скиллов.

---

## 11. Definition of Done + как Codex генерит скилл из регламента

**DoD слоя правил:**
- `_base` поднимается, harness резолвит профиль, `augment/prepare/validate` зовутся движком по namespaced-стадиям.
- `kids` и `commerce` резолвятся как оверлеи (override/disable/add/params/program_types работают).
- `readme_structure/check.py` ловит структурные дефекты, `document_integrity/check.py` — N.1–N.5, `visual_quality/check.py` — низкое разрешение, всё на эталонных «битых» входах.
- Issues из `check.py` поднимают `human_review_required` в гейте.
- CI: producer-скилл (`produces`) не привязан к `generator.*`; каждый `requires` кем-то производится.
- Inner-loop чинит структурный провал без полной регенерации; outer-loop (жюри) — один проход.

**Рецепт для Codex (на каждый скилл):**
1. Взять строку из таблицы §8 → открыть указанную секцию регламента (`source`).
2. Прозу секции → `instructions.md` (правила для модели, с `{{param}}`-плейсхолдерами).
3. Числовые/структурные требования → `check.py` (детерминированно, возврат `[RuleIssue]`).
4. Хуки/стадии (namespaced!)/severity/params → `skill.yaml` строго по строке таблицы.
5. Per-направление дельты → в `kids/`/`commerce/` как `params` (предпочтительно) или папка-оверрайд, **не** трогая `_base`.
6. Один скилл = одна папка = одна Codex-сессия; не превышать ~150 строк `check.py` на скилл.
