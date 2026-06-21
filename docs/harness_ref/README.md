# harness — рантайм слоя правил (исполнимый, тесты 5/5)

Минимальный рантайм по `SKILLS_ARCHITECTURE.md` §5.2 + §6: грузит skill-папки, резолвит профиль,
маршрутизирует по namespaced-стадиям, файрит хуки. Это то, что превращает декларативные скиллы в
работающую вещь — и место, где дешевле всего зафиксировать семантику до генерации остальных скиллов.

## Запуск
```bash
PYTHONPATH=. python3 tests/test_harness.py        # или pytest
```

## Что внутри
```
core/methodology/
├── rules.py        # контракт RuleIssue / GeneratedDoc / DocImage
├── harness.py      # load_skill / resolve_profile / Harness  (~190 строк)
└── profiles/
    ├── _base/      # Основа: 6 скиллов (voice, visual_quality, competency_weights — РЕАЛЬНЫЕ; readme_structure, document_integrity, audience_level — заглушки skill.yaml)
    ├── kids/       # оверлей: voice-override + 5 adds + program_types
    └── commerce/   # оверлей: только param (readme_cyclic), без папок
tests/test_harness.py
```
> Реальные `readme_structure` / `visual_quality` / `document_integrity` из прошлых поставок кладутся
> в `profiles/_base/skills/`; здесь часть из них — заглушки, чтобы дерево осталось компактным.

## Контракт кода скилла (модуль `check.py`, всё опционально)
```python
check(doc, params)   -> list[RuleIssue]   # для at: post.validate
prepare(ctx, params) -> dict              # для at: pre.stage (возвращает обновления контекста)
# at: prompt.augment кода не требует — берёт instructions.md, рендерит {{param}} из params
```

## API харнесса
```python
rp = resolve_profile("kids", PROFILES_ROOT, program_type="main")   # §5.2
h  = Harness(rp)
h.augment("generator.theory", ctx)        -> str            # склейка instructions
h.prepare("curriculum.planner", ctx)      -> ctx'           # producer пишет контекст
h.validate("generator.evaluation", doc)   -> list[RuleIssue] # машинные проверки -> в гейт
h.producers_bound_to("generator.")        -> []             # CI-инвариант
```

## Что проверяют тесты (два ключевых инварианта + 3 опорных)
1. **Резолвинг Дети** — base + `disables` + `overrides` + `adds` + program_type + dotted-params: `readme_structure` выключен, 5 скиллов добавлены, `voice` — детский override, `assessments.required`/`lesson_structure.lesson_hours` пришли из `program_type.main`, `content_model=lesson_course`, `terminology.branch=программа`.
2. **Producer невидим генератору** — `competency_weights` (`produces`) привязан только к `curriculum.planner`; не утекает ни в одну `generator.*`-стадию; `producers_bound_to("generator.")==[]`; `prepare()` на planner пишет `curriculum.competency_weights` (сумма=100). Генератор веса ЧИТАЕТ, не пересчитывает.
3. `master_class` → `lesson_single` + `duration_minutes=90`.
4. Коммерция → `readme_cyclic` ОДНИМ параметром (без подмены папки).
5. Харнесс реально гоняет `augment` (рендерит `{{formality}}`) и `validate` (реальный `visual_quality.check` ловит картинку 400×300).

## Поймано при сборке: ключ хука — `at`, не `on`
YAML 1.1 (PyYAML по умолчанию) приводит голый `on:` к булеву `True` («Norway problem», как у GitHub
Actions) → `h["on"]` падает. Поэтому хук-элемент пишется `- at: <hook>`, без кавычек-костылей.
**Это правка спека и трёх ранее отданных скиллов** (механически `sed -E 's/- on:/- at:/'`). В спеке
уже исправлено.

## Решения резолвинга (зафиксированы в коде)
- **Порядок параметров:** `skill.yaml.params` → `profile.params` (base→derived) → `program_type.params`. Позже побеждает.
- **content_model:** активный из program_type инжектится как ДЕФОЛТ в скиллы, что его декларируют; затем dotted-оверрайд побеждает (так Коммерция ставит `readme_cyclic`).
- **applies_to.artifact_family:** скилл отбрасывается, если активный family (из content_model) не в его списке.
