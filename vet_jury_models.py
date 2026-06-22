#!/usr/bin/env python3
"""
vet_jury_models.py — отсев кандидатов в дидактическое жюри по русскому + стабильному JSON.

Идея: даём каждой модели 3 коротких README-фрагмента ИЗВЕСТНОГО качества и просим
дидактическую оценку 1..5 в строгом JSON. Хорошая для жюри модель должна:
  (1) вернуть валидный JSON 3/3 раз,
  (2) поставить оценки в правильном ПОРЯДКЕ: good > borderline > bad,
  (3) поймать AI-воду в плохом фрагменте,
  (4) написать осмысленный rationale на русском (это смотришь глазами).

Запуск:
  python vet_jury_models.py google/gemini-3.1-flash-lite-preview deepseek/deepseek-v4-pro qwen/qwen3.6-plus

OPENROUTER_API_KEY или OPEN_ROUTER_API_KEY берётся из env или из локального .env.
"""
import os, sys, json, re, urllib.request, urllib.error
from pathlib import Path

API = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_MODELS = [
    "google/gemini-3.1-flash-lite-preview",
    "deepseek/deepseek-v4-pro",
    "qwen/qwen3.6-plus",
]

def load_openrouter_key():
    for name in ("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"):
        key = os.environ.get(name, "").strip()
        if key:
            return key
    env_path = Path(".env")
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() in {"OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"}:
            return value.strip().strip("\"'")
    return ""

KEY = load_openrouter_key()

# --- 3 фрагмента известного качества (направление оценки зашито в expect) ---
FRAGMENTS = [
    {
        "id": "good",
        "expect": "высокая (4-5), мало замечаний",
        "text": (
            "## Переменные\n"
            "Цель: научиться хранить значение под именем и переиспользовать его.\n"
            "Переменная — это подписанная коробка: кладём значение, достаём по имени.\n"
            "Сначала самое простое: `age = 25` — теперь `age` хранит 25. "
            "Меняем: `age = 26` — коробка та же, значение новое.\n"
            "Зачем: чтобы не повторять число в десяти местах, а поменять в одном.\n"
            "Задача: заведи переменную `price = 100`, выведи её, затем увеличь на 50 и выведи снова. "
            "Ожидаемый вывод: 100, затем 150."
        ),
    },
    {
        "id": "bad",
        "expect": "низкая (1-2): AI-вода, нет scaffolding, теория не связана с практикой",
        "text": (
            "## Введение в переменные\n"
            "В современном мире программирование играет ключевую роль, и понимание переменных "
            "является фундаментально важным навыком для каждого начинающего разработчика. "
            "Переменные — это мощный и гибкий инструмент, который открывает безграничные возможности. "
            "Освоив эту тему, вы сделаете уверенный шаг к успешной карьере в IT и сможете решать "
            "широкий спектр задач. Важно отметить, что переменные используются повсеместно. "
            "Задача: подумайте, насколько важны переменные в программировании."
        ),
    },
    {
        "id": "borderline",
        "expect": "средняя (3): теория есть, но прыжок сложности без подводки, практика слабая",
        "text": (
            "## Рекурсия\n"
            "Рекурсия — это когда функция вызывает саму себя.\n"
            "Пример: факториал через рекурсию с мемоизацией и хвостовой оптимизацией:\n"
            "`def f(n, acc=1): return acc if n==0 else f(n-1, acc*n)`.\n"
            "Здесь мы накапливаем результат в аккумуляторе, чтобы избежать переполнения стека.\n"
            "Задача: реализуйте факториал."
        ),
    },
]

JURY_PROMPT = (
    "Ты — дидактический эксперт. Оцени учебный фрагмент README на русском по дидактике: "
    "scaffolding (нарастание сложности), наличие AI-воды/общих слов, связь теории с практикой, "
    "конкретность задачи. Верни ТОЛЬКО JSON по схеме, без пояснений вокруг:\n"
    '{"didactic_score": <целое 1..5>, "weaknesses": [<строки>], "strengths": [<строки>], '
    '"rationale": "<кратко по-русски>"}'
)

SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "didactic_verdict",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "didactic_score": {"type": "integer", "minimum": 1, "maximum": 5},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
            },
            "required": ["didactic_score", "weaknesses", "strengths", "rationale"],
            "additionalProperties": False,
        },
    },
}

def call(model, fragment_text, use_schema=True):
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": JURY_PROMPT},
            {"role": "user", "content": fragment_text},
        ],
        "temperature": 0,
    }
    if use_schema:
        body["response_format"] = SCHEMA
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]

def parse_json(txt):
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)  # repair: вытащить первый {...}
        if m:
            try: return json.loads(m.group(0))
            except Exception: return None
        return None

def vet(model):
    print(f"\n{'='*70}\nМОДЕЛЬ: {model}\n{'='*70}")
    scores, json_ok, bad_caught = {}, 0, False
    for fr in FRAGMENTS:
        verdict, raw = None, ""
        for use_schema in (True, False):  # сначала со схемой, при ошибке — без + repair-parse
            try:
                raw = call(model, fr["text"], use_schema)
                verdict = parse_json(raw)
                if verdict: break
            except urllib.error.HTTPError as e:
                raw = f"HTTP {e.code}: {e.read().decode()[:200]}"
            except Exception as e:
                raw = f"ERR: {e}"
        if verdict and isinstance(verdict.get("didactic_score"), int):
            json_ok += 1
            scores[fr["id"]] = verdict["didactic_score"]
            if fr["id"] == "bad":
                blob = json.dumps(verdict, ensure_ascii=False).lower()
                bad_caught = any(k in blob for k in ["вод", "общи", "scaffold", "связ", "конкрет", "абстрак"])
            print(f"  [{fr['id']:10}] score={verdict['didactic_score']} "
                  f"(ожид: {fr['expect']})")
            print(f"             rationale: {verdict.get('rationale','')[:120]}")
        else:
            scores[fr["id"]] = None
            print(f"  [{fr['id']:10}] JSON НЕ РАСПАРСИЛСЯ -> {raw[:120]}")
    # вердикт пригодности
    order_ok = (None not in scores.values()
                and scores["good"] > scores["borderline"] > scores["bad"])
    print(f"\n  ИТОГ {model}:")
    print(f"    JSON валиден:        {json_ok}/3 {'✓' if json_ok==3 else '✗ (нестабилен)'}")
    print(f"    Порядок good>bord>bad: {'✓' if order_ok else '✗ (не различает качество)'}")
    print(f"    AI-вода поймана:     {'✓' if bad_caught else '✗ (не увидел воду)'}")
    ok = json_ok == 3 and order_ok and bad_caught
    print(f"    ПРИГОДНА ДЛЯ ЖЮРИ:   {'ДА ✓' if ok else 'НЕТ ✗ — глазами проверь rationale на русском'}")
    return ok

if __name__ == "__main__":
    if not KEY:
        sys.exit("Нет OPENROUTER_API_KEY/OPEN_ROUTER_API_KEY в env или .env.")
    models = sys.argv[1:] or DEFAULT_MODELS
    results = {m: vet(m) for m in models}
    print(f"\n{'='*70}\nСВОДКА\n{'='*70}")
    for m, ok in results.items():
        print(f"  {'✓ годна' if ok else '✗ под вопрос'}  {m}")
    print("\nГодные -> в jury_models. '✗' — открой rationale выше: если русский поплыл "
          "или вода не поймана, замени на Anthropic/Google/Mistral.")
