# GitNexus — как пользоваться

MCP-сервер + CLI, который строит **граф кода** (вызовы, импорты, наследование, реализации
интерфейсов, кластеры, execution-flows) и даёт инструменты для навигации и **blast-radius**
анализа. Заменил graphify: граф строится **детерминированно** (Tree-sitter AST + резолв),
**без LLM, без API-ключа, без расхода подписок** — секунды вместо часов.

Репозиторий: [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus).

---

## Однократно на машине (уже сделано)

```powershell
# 1. CLI глобально (npm). Бинарь: C:\Users\zvp\AppData\Roaming\npm\gitnexus
npm install -g gitnexus@latest

# 2. MCP на уровне пользователя — доступен во ВСЕХ проектах
claude mcp add gitnexus --scope user -- gitnexus mcp
```

> MCP подключается автоматически в любом проекте. Где индекса ещё нет — построй его
> (`gitnexus analyze`) и перезапусти Claude Code.

---

## Для каждого проекта

### 1. Построить индекс
```powershell
cd C:\путь\к\проекту
gitnexus analyze            # инкрементально, секунды; полный ребилд: gitnexus analyze --force
```
Результат: встроенная БД в `.gitnexus/` (в `.gitignore`). LLM/ключ не нужен.

### 2. Перезапустить Claude Code → проверка
```powershell
claude mcp get gitnexus     # ожидаем: √ Connected
gitnexus status             # статус индекса текущего репо
```

### 3. Пользоваться (Claude сам вызовет MCP-инструмент; есть и CLI)

| Вопрос / задача | CLI | смысл |
|---|---|---|
| что сломается, если поменять X | `gitnexus impact <symbol>` | blast radius (главное для рефактора) |
| кто вызывает / что вызывает символ | `gitnexus context <name>` | 360° по символу (callers+callees+процессы) |
| как связаны A и B | `gitnexus trace <A> <B>` | кратчайший путь по вызовам |
| где в коде про «…» | `gitnexus query "<concept>"` | поиск execution-flows |
| что задел мой git-diff | `gitnexus detect-changes` | diff → затронутые символы/flows (pre-commit) |
| произвольный запрос к графу | `gitnexus cypher "<Cypher>"` | сырой Cypher по LadybugDB |

### 4. После изменений кода
```powershell
gitnexus analyze            # инкрементально подхватит изменения (git-aware)
```
Граф дёшево держать **свежим** — делай это в активном рефакторе перед каждым `impact`.

---

## Рефактор: рабочая связка

GitNexus даёт **структурный** граф. Динамику Python (DI, `getattr`, строковые реестры,
Jinja, ORM-связи) статикой не покрыть полностью — поэтому:

> **gitnexus impact** (структурный blast radius) **+ pyright** (типовые поломки) **+ grep**
> (строковая/динамическая развязка). Этого хватает для безопасных перемещений.

---

## Шпаргалка
- MCP зарегистрирован один раз (`--scope user`) — на проект только `gitnexus analyze`.
- Один проект = свой `.gitnexus/` (берётся из cwd).
- Снести индекс: `gitnexus clean` (в репо) или `gitnexus remove <target>`.
- Список репо: `gitnexus list`. Возможности рантайма: `gitnexus doctor`.
- Авто-настройка под несколько агентов (Cursor/Codex/OpenCode): `gitnexus setup` —
  мы её НЕ использовали (пишет секции в AGENTS.md/хуки); зарегистрировали MCP вручную.
- Веб-демо без установки: gitnexus.vercel.app (drag-n-drop репо/ZIP).
- Опц. `gitnexus wiki` — единственная фича, которой нужен LLM-ключ.

> Codex-паритет (`~/.codex`) пока НЕ настроен. `gitnexus setup -c codex` умеет, если решим.
