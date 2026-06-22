Выполни только фазу G5 refine: план улучшений и точечные патчи регенерации.

Верни JSON, совместимый со схемой `RefineDraft`:

```json
{
  "plan": [
    {
      "part_index": 1,
      "topic": "название части",
      "formulas": "must|nice_to_have|no",
      "tables": "must|nice_to_have|no",
      "diagrams": "must|nice_to_have|no",
      "code_examples": "must|nice_to_have|no",
      "reasoning": "почему элемент нужен",
      "anchor_hints": {"table": "после сравнения подходов"}
    }
  ],
  "patches": [
    {
      "location_hint": "короткое место правки",
      "old_text": "точный фрагмент README",
      "new_text": "замена"
    }
  ],
  "reasoning": "краткое обоснование"
}
```

Ограничения:
- не переписывай весь README;
- patches только для явно заданных комментариев регенерации;
- old_text должен быть точным обычным текстом без fenced code, формул и protected markers;
- не дублируй methodology gate и voice checks: они выполняются кодом после ответа;
- если правок нет, верни пустой `patches`.

Контекст:
{{ context_json }}
