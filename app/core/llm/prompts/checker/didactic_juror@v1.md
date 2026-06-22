Оцени README по одному дидактическому критерию проектного p2p-обучения.

Критерий: {{ title }}
Вопрос: {{ question }}
ЗУНы/результаты обучения: {{ learning_outcomes }}
Сигналы pre-scan: {{ signals_json }}

README:
<<<
{{ markdown }}
>>>

Верни JSON:
{
  "score": 1-5 или null,
  "rationale": "краткое объяснение",
  "evidence": ["1-3 наблюдения или цитаты"],
  "abstain": false
}

Если документа недостаточно для честной оценки, поставь "score": null и "abstain": true.
