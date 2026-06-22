Проверь практические задания после генерации.

Верни только JSON, совместимый со схемой `PracticeCriticResponse`:

```json
{
  "issues": [
    {
      "task_index": 1,
      "kind": "p2p_check",
      "severity": "error",
      "message": "что не так",
      "suggestion": "как исправить"
    }
  ]
}
```

Разрешённые `kind`:
- `p2p_check` — критерии не наблюдаемы или нельзя проверить на peer review;
- `theory_alignment` — задача не использует темы/понятия Главы 2;
- `story_alignment` — нет рабочей ситуации, роли или ограничения;
- `sjm_alignment` — потерян SJM-кейс;
- `raw_input` — во входных данных есть готовое решение/processed material;
- `goal` — цель пассивная, учебно-абстрактная или не проверяемая;
- `artifact` — ожидаемый результат без конкретного артефакта и пути.

Не ругай задания за отсутствие bonus/dataset/code examples: это отдельные этапы.
Не дублируй проблему, если она уже исправлена deterministic contract: путь есть, критерии наблюдаемы, theory_support заполнен.

Контекст:
{{ context_json }}
