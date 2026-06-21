"""Тест-образец document_integrity. Скилл грузится динамически (как harness). pytest или __main__."""
import importlib.util
from pathlib import Path

import yaml

from core.methodology.rules import GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "core/methodology/profiles/_base/skills/document_integrity"


def load():
    params = yaml.safe_load((SKILL / "skill.yaml").read_text(encoding="utf-8"))["params"]
    spec = importlib.util.spec_from_file_location("di_check", SKILL / "check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return params, mod.check


def hard(issues):
    return sorted(i.code for i in issues if i.severity == "hard")


def codes(issues):
    return {i.code for i in issues}


# ===== чистый README-подобный документ =====
CLEAN_README = """# Проект DO4_LinuxMonitoring

Аннотация проекта по мониторингу Linux-систем для начинающих администраторов.

## Содержание
- Теория
- Практика

## Схема monitoring
Ниже архитектура связки сбора метрик и хранилища.

```mermaid
graph TD
  Agent --> monitoring
  monitoring --> Storage
```

## Сравнение инструментов

| Инструмент | Назначение |
|---|---|
| Prometheus | сбор метрик |
| Grafana | визуализация |

Текст проекта DO4_LinuxMonitoring последовательно ведёт от установки агента к настройке
дашбордов, без «провисаний». Все шаги опираются на предыдущие и складываются в рабочий стенд.
"""

# ===== чистый lesson-подобный документ (другой artifact_family, тот же скилл) =====
CLEAN_LESSON = """# Программа «Юный программист» T12_ScratchStart

Аннотация программы для детей 9–11 лет по основам визуального программирования.

## Занятие 1. Знакомство со средой
Дети запускают среду и собирают первую сцену. Наставник показывает интерфейс и помогает
повторить шаги. К концу занятия каждый ученик имеет собственную мини-сцену с персонажем.

## Занятие 2. Движение персонажа
Ученики добавляют управление и анимацию движения, разбирают понятие события и цикла на
понятных примерах. Занятие закрепляет навык через индивидуальную мини-практику с проверкой.
"""

# ===== битый документ: все пять дефектов =====
BROKEN = """# Проект DO4_LinuxMonitoring

Аннотация. TODO: дописать введение.

## Таблица
| Инструмент | Назначение |
|---|---|
| Prometheus | сбор метрик | лишняя колонка |
| Grafana |

## Архитектура
```mermaid
graph TD
  X --> Y
```

Этот абзац является достаточно длинным повторяющимся блоком текста, который встречается в
документе дважды подряд для проверки детектора дословных повторов и template bleed внутри файла.

Этот абзац является достаточно длинным повторяющимся блоком текста, который встречается в
документе дважды подряд для проверки детектора дословных повторов и template bleed внутри файла.

В проект случайно затесался чужой идентификатор T12_ScratchStart из другой программы, и эта
фраза обрывается на союзе и
"""


def test_clean_readme_no_hard():
    params, check = load()
    issues = check(GeneratedDoc(markdown=CLEAN_README, project_id="DO4_LinuxMonitoring"), params)
    assert hard(issues) == [], f"ожидалось чисто, получено: {hard(issues)}"


def test_clean_lesson_no_hard():
    params, check = load()
    # тот же скилл на другом artifact_family (lesson) — целостность не зависит от каркаса
    issues = check(GeneratedDoc(markdown=CLEAN_LESSON, project_id="T12_ScratchStart"), params)
    assert hard(issues) == [], f"lesson ожидался чистым, получено: {hard(issues)}"


def test_broken_is_caught():
    params, check = load()
    c = codes(check(GeneratedDoc(markdown=BROKEN, project_id="DO4_LinuxMonitoring"), params))
    for expected in {
        "document_integrity.table_columns",      # N.1 рваная таблица
        "document_integrity.placeholder",         # N.2 TODO
        "document_integrity.repeated_block",      # N.2 дословный повтор
        "document_integrity.foreign_project_id",  # N.5 чужой id
    }:
        assert expected in c, f"не пойман {expected}; пойманы: {sorted(c)}"


def test_diagram_without_context():
    params, check = load()
    # заголовок далеко (>6 строк) от диаграммы -> в окне контекста его нет
    filler = "\n".join(f"Строка {n} обычного текста без заголовка." for n in range(1, 8))
    md = f"# Док T01_Demo\n\n{filler}\n\n```mermaid\ngraph TD\n A-->B\n```\n"
    c = codes(check(GeneratedDoc(markdown=md), params))
    assert "document_integrity.diagram_no_context" in c, sorted(c)


def test_unclosed_fence():
    params, check = load()
    md = "# Док\n\n```python\nprint('oops, no closing fence')\n"
    c = codes(check(GeneratedDoc(markdown=md), params))
    assert "document_integrity.unclosed_fence" in c, sorted(c)


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t(); print(f"  PASS  {t.__name__}"); passed += 1
        except Exception:
            print(f"  FAIL  {t.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
