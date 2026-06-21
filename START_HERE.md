# START_HERE.md — как устроен репозиторий и как ставить задачи Codex

> Положить в **корень** репо `S21_factory/`. Отвечает на: что под что, что удалить, куда регламенты,
> и как сформулировать задачу для Codex.

## Главный принцип: две зоны

| Зона | Что это | Codex |
|---|---|---|
| `docs/` | спека, план, регламенты, **эталоны** | **только читает**, никогда не редактирует |
| корень + `app/` | сам монорепо (его ещё нет — создаёт волна 0) | **строит сюда** |

`to_do/` — это сейчас свалка из обеих зон. Переименуй `to_do/` → `docs/` и наведи порядок ниже.
**`AGENTS.md` — в КОРЕНЬ** репо (не в `docs/`): Codex и Claude Code автоматически читают `AGENTS.md`
из корня каждую сессию. Внутри `docs/` он не подхватится.

## Шаг 1 — удалить дубли-ландмайны (сплющенные копии из «показа по файлу»)

Эти файлы в корне `to_do/` — плоские копии того, что уже лежит структурно внутри папок. Codex
примет их за настоящие и запутается. Удалить:

```
to_do/check.py                 # = document_integrity_skill/.../skills/document_integrity/check.py
to_do/skill.yaml               # = тот же document_integrity skill.yaml
to_do/harness.py               # = harness_ref/core/methodology/harness.py
to_do/test_harness.py          # = harness_ref/tests/test_harness.py
to_do/README.md                # = harness_ref/README.md
to_do/CONSOLIDATION_PLAN.md    # СТАРАЯ версия (§11 открыт)
```
И переименуй: `CONSOLIDATION_PLAN (1).md` → `CONSOLIDATION_PLAN.md` (это **новая**, §11 закрыт).

## Шаг 2 — целевая раскладка

```
S21_factory/
├── AGENTS.md                      ← В КОРЕНЬ (правила; Codex читает автоматически)
├── START_HERE.md                  ← этот файл
├── docs/                          ← бывший to_do/, ТОЛЬКО ЧТЕНИЕ
│   ├── CONSOLIDATION_PLAN.md       (волны + DoD)
│   ├── SKILLS_ARCHITECTURE.md      (слой правил: skills/hooks/harness/profiles)
│   ├── TASKS.md                    (атомарные задачи — отсюда берёшь по одной)
│   ├── DECISIONS.md                (закрытые решения §11)
│   ├── regulations/                ← ДОБАВИТЬ (см. шаг 3): входные данные для скиллов
│   │   ├── osnova.md  deti.md  commerce.md
│   ├── notebooks/                  ← ДОБАВИТЬ: 3 .ipynb (источник осей чекера, волна 5)
│   └── reference/                  ← рабочие ЭТАЛОНЫ (Codex копирует паттерн отсюда)
│       ├── harness_ref/            (harness + контракт + 3 профиля; тесты 5/5)
│       └── document_integrity_skill/
└── app/  migrations/  tests/  static/   ← создаёт волна 0 (T0.1)
```

`docs/reference/harness_ref/` — самый полный эталон (все профили + рабочий harness).
`document_integrity_skill/` добавляет `document_integrity/check.py` и поле `project_id` на
`GeneratedDoc` — при T1.1/TM.1 они сливаются в один `app/core/methodology/`.

## Шаг 3 — документы: грузить или нет

**Да, грузить — но как `.md`, не `.docx`.** Скиллы *генерируются из* регламентов (рецепт TM.2:
проза секции → `instructions.md`, числа → `check.py`). Без текста регламентов Codex не сможет
написать `voice`/`checklist`/`lesson_structure` достоверно. `.docx` — бинарь-zip, Codex читает его
плохо и не диффит; `.md` — то, что нужно.

| Документ | Куда | Кто потребляет |
|---|---|---|
| Регламенты Основа/Дети/Коммерция (`.md`) | `docs/regulations/` | TM.2 (генерация скиллов), TM.3 (профили kids/commerce) |
| 3 ноутбука (structural_criteria_v2, didactic jury/prototype) | `docs/notebooks/` | волна 5 (две оси чекера) |

Готовые `.md`-экстракты трёх регламентов — в приложенном архиве, просто распакуй в `docs/regulations/`.
(Связь «какой скилл из какой секции» уже расписана в `SKILLS_ARCHITECTURE.md §8`.)

## Шаг 4 — как поставить задачу Codex (переиспользуемый промпт)

Codex читает `AGENTS.md` из корня сам. Задача — всегда ОДНА из `docs/TASKS.md`. Шаблон:

```
Реализуй задачу <ID> из docs/TASKS.md (например, T0.1).

Сначала прочитай:
- AGENTS.md (правила — соблюдай ВСЕ)
- строку задачи <ID> в docs/TASKS.md: вход, файлы, бюджет строк, «Образец», DoD
- «Образец» из строки задачи (если указан) — копируй паттерн из docs/reference/, не изобретай
- релевантную секцию docs/CONSOLIDATION_PLAN.md или docs/SKILLS_ARCHITECTURE.md

Сделай ТОЛЬКО эту задачу. Не трогай другие модули. Уложись в бюджет строк.
Заверши тестом (один «чистый» вход + один «битый») — зелёный тест входит в DoD.
НЕ бери следующую задачу.
```

Меняешь только `<ID>` и берёшь задачи по порядку зависимостей из TASKS.md
(`0 → 1 ∥ M → 2 → …`). Один прогон Codex = одна задача.

## Шаг 5 — первая задача

`T0.1` (скелет монорепо) → затем `T0.2` (реестр модулей) → `T1.1`/`TM.1` (перенести готовый harness +
3 эталона в `app/core/methodology/`, прогнать `test_harness.py` 5/5 в репо). После этого волна M
(скиллы из §8) и волна 2 (УП) идут по образцу.

> Перед волной 5 закрой единственный внешний «подтвердить» из `DECISIONS.md D4` — слаги OpenRouter и
> `GENERATOR_MODEL`. Остальные «подтвердить» (baseline бассейна, hours_band, живой ли viewer) всплывут
> по ходу и старт не держат.
