# AGENTS.md — рабочее соглашение (читать в начале каждой сессии)

> Применимо к Codex/Claude Code в этом репозитории. Скопировать в `CLAUDE.md` для Claude Code.
> Контекст задач — `TASKS.md`; архитектура — `CONSOLIDATION_PLAN.md`, `SKILLS_ARCHITECTURE.md`.

## Миссия
Слить `Spravochnik` + `Content_generator_ver2.4` в один модульный монорепо: единая PG, единый UI,
ядро + вертикальные модули-фичи. **Перенести весь функционал, компактно** (~81k → ~30–32k строк за
счёт удаления дублей и императивщины, а не функций). Раздувание — главный антипаттерн.

## Девять железных правил

1. **Одна сессия = одна задача из `TASKS.md` = один модуль.** Не браться за следующую, пока тест
   текущей не зелёный и бюджет не соблюдён. Не трогать чужие модули в рамках задачи.
2. **Сначала прочитать, потом писать.** Перед написанием аналога — открыть «Образец» из задачи и
   сделать `grep`: возможно, это уже есть. Не изобретать готовое (harness, 3 эталонных скилла, gate).
3. **Бюджет строк — закон.** Значения в `line_budget.yaml` (из `CONSOLIDATION_PLAN §2`). PR сверх
   бюджета не мёржится без явного `budget-override:` с обоснованием в описании PR.
4. **Данные вместо кода; декларативное вместо императивного.** Структура артефакта — yaml/json, а не
   python-чекеры. Пороги — в `thresholds.yaml`. Промпт — в `prompts/<area>/<name>@v1.md`, не в строке.
5. **Переиспользовать, не дублировать.** Один LLM-клиент, один gate, одна alembic-цепочка, один
   `signals.py` на эвристики. Две модели навыка → одна. Нашёл копипасту — вынеси, не размножай.
6. **Зависимости строго в одну сторону:** `core ← {curriculum, generator, checker, reference}`.
   `core/*` НЕ импортирует `modules/*` — знает только абстракции (`GeneratedDoc`, `RuleIssue`,
   `MethodologyContext`, `ArtifactRef`). Модули сами адаптируют свои данные к ним.
7. **Каждая задача приносит тест.** Минимум: один «чистый» вход (ожидаемо пусто/ок) + один «битый»
   (каждый код ловится). Зелёный тест — часть DoD, не опция.
8. **Producer пишет контекст — downstream читает.** Planner-скиллы (`pre.stage`/`curriculum.planner`)
   считают и пишут в контекст (`produces`); генератор читает из `CurriculumContext`, не пересчитывает.
   Ни один скилл не исполняется дважды.
9. **Две оси не складываются.** Структурная (скрипт, «не сломано») и дидактическая (жюри, «хорошо ли
   преподано») — раздельные числа. `39/39` при `2.6/5` — валидный результат.

## Контракты (нарушение = провал ревью)

- **skill.yaml:** ключ хука — `at:`, **не `on:`** (YAML 1.1 приводит голый `on` к булеву `True`).
  Стадии namespaced: `<consumer>.<stage>` (`curriculum.planner`, `generator.evaluation`,
  `checker.evaluation`). `severity: hard|soft`. Параметры в `params`, переопределяемы профилем dotted.
- **check.py:** одна функция `check(doc, params) -> list[RuleIssue]`, детерминированно, без сети/LLM,
  ≤150 строк. Producer-скилл: `prepare(ctx, params) -> dict`. Образцы — три эталонных скилла.
- **Терминология:** *methodology skill* (правило) ≠ *competency* (навык студента из Справочника).
  В коде/БД competency называется `competency_*`, никогда `skill`.
- **content_model** — свойство artifact_target, не профиля. Новый content_model заводится ТОЛЬКО при
  различии обязательных разделов верхнего уровня; различие порогов/счётчиков → `params`.

## CI-гейты (TX.1–TX.3)
`line_budget.yaml` · grep-запреты (inline-промпты вне `prompts/`; SQL вне repo-слоя; `core→modules`;
`on:` в skill.yaml) · дубль-детектор. Приёмочный тест волны (`CONSOLIDATION_PLAN §6`) обязателен.

## Чего НЕ делать (failure modes)
- Не раздувать ради «полноты»: лишний слой абстракции, ось-таксономия там, где хватает параметра,
  пересказ регламента в код вместо ссылки на секцию.
- Не плодить `content_model`, где разница в `params` (тест на запах: `if type==X: skip 6 разделов` →
  модель; `if type==X: threshold=Y` → параметр).
- Не дебатить структурную ось (сломанная таблица не нуждается в трёх моделях). Не рефлексировать над
  рефлексией (inner-loop 1–2 итерации, outer один проход). ReAct в генерации — сознательно за бортом.
- Не класть control-flow в скиллы (скилл — спека; *как* агент сходится — дело движка).
- Не возвращать удалённое: Jaccard-граф, section1-4 checkers, второй LLM-клиент, второй манифест.

## Универсальный Definition of Done
Код + зелёный тест (clean + битый) + в бюджете + нет нарушений grep-гейтов + выполнен DoD из задачи
`TASKS.md`. Только тогда задача закрыта и можно брать следующую.

## Целевая структура (напоминание)
```
app/
├── core/{db,llm,models,config,methodology,ui}   # ядро, без знания о фичах
│   └── methodology/{harness.py,rules.py,profiles/{_base,kids,commerce}/skills/<id>/}
├── modules/{generator,checker,translator,curriculum,reference}/  # вертикальные срезы
│   └── <module>/{router.py,service.py,pipeline/,panel.{html,js},manifest.py}
├── static/   migrations/   tests/
```
Добавить модуль = папка в `modules/` + `manifest.py` в `MODULE_REGISTRY`. Добавить правило = папка
скилла + строчка хука. Добавить направление = `profile.yaml` + папки-оверрайды.

## Команды и проверки (тулинг)

Стек: **pip + `pyproject.toml`** (НЕ uv/poetry), FastAPI (`app.main:app`), SQLite + **alembic**.
- Установка: `pip install -e .` (или `pip install -r requirements.txt`)
- Запуск API: `uvicorn app.main:app --reload`
- Тесты: `pytest` (конфиг `[tool.pytest.ini_options]`) — зелёный тест входит в DoD (см. правило 7).
- Линт: `ruff check .` (конфиг `[tool.ruff]`); автofix: `ruff check --fix .`
- Типы: pyright/mypy не настроены — при необходимости `pyright app`, иначе пропустить.
- Миграции: `alembic revision --autogenerate -m "..."` (обратимая), `alembic upgrade head` — одна цепочка (правило 5), без потери данных.

Quality gate перед закрытием задачи: `ruff check .` + `pytest` зелёные, бюджет строк соблюдён,
grep-гейты не нарушены (CI TX.1–TX.3). Эти команды — дополнение к DoD выше, а не замена.

## Инструменты Codex (MCP/скиллы, если подняты)
**graphify** (граф кода, влияние изменений) · **serena** (семантика символов) · **context7**
(доки библиотек) · **gbrain** (память между сессиями). Для слияния/рефактора ядра — скилл
`merge-and-refactor` (он и есть про текущую миссию монорепо).

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Content_factory** (19174 symbols, 38284 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Content_factory/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Content_factory/clusters` | All functional areas |
| `gitnexus://repo/Content_factory/processes` | All execution flows |
| `gitnexus://repo/Content_factory/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
