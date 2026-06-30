"""C3 didactic debate: critic / defender / judge on different models."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.llm import StructuredPrompt, complete_typed, load_prompt
from app.core.llm.client import create_llm_client

ClientFactory = Callable[[str], Any]


class DebateTurn(BaseModel):
    """One role turn in a didactic escalation transcript."""

    model_config = ConfigDict(extra="forbid")

    role: str
    model: str
    content: list[str] | str


class DebateResult(BaseModel):
    """Final debate verdict for one dimension."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    final_score: float
    rationale: str
    transcript: list[DebateTurn] = Field(default_factory=list)


class DebatePoints(BaseModel):
    """Structured critic/defender output."""

    model_config = ConfigDict(extra="forbid")

    points: list[str] = Field(default_factory=list)


class DebateJudgeOutput(BaseModel):
    """Structured judge output."""

    model_config = ConfigDict(extra="forbid")

    score: float
    rationale: str = ""

    @field_validator("score")
    @classmethod
    def _score_range(cls, value: float) -> float:
        return max(1.0, min(5.0, float(value)))


def run_debate(
    *,
    dimension: str,
    title: str,
    question: str,
    markdown: str,
    signals: dict[str, Any],
    jury_scores: dict[str, float | None],
    config: Any,
    learning_outcomes: list[str] | None = None,
    client_factory: ClientFactory | None = None,
) -> DebateResult:
    """Escalate a disputed dimension to critic/defender/judge models."""

    roles = dict(getattr(config, "debate_roles", {}) or {})
    try:
        critic = _call_points(
            model=roles["critic"],
            prompt_name="didactic_debate_critic",
            title=title,
            question=question,
            markdown=markdown,
            signals=signals,
            jury_scores=jury_scores,
            config=config,
            client_factory=client_factory,
        )
        defender = _call_points(
            model=roles["defender"],
            prompt_name="didactic_debate_defender",
            title=title,
            question=question,
            markdown=markdown,
            signals=signals,
            jury_scores=jury_scores,
            config=config,
            client_factory=client_factory,
            critic=critic,
        )
        judge = _call_judge(
            model=roles["judge"],
            title=title,
            question=question,
            signals=signals,
            jury_scores=jury_scores,
            critic=critic,
            defender=defender,
            config=config,
            client_factory=client_factory,
        )
        return DebateResult(
            dimension=dimension,
            final_score=judge.score,
            rationale=judge.rationale,
            transcript=[
                DebateTurn(role="critic", model=roles["critic"], content=critic.points),
                DebateTurn(role="defender", model=roles["defender"], content=defender.points),
                DebateTurn(role="judge", model=roles["judge"], content=judge.rationale),
            ],
        )
    except Exception:
        return _fallback_debate(dimension=dimension, jury_scores=jury_scores, signals=signals, roles=roles)


def _call_points(
    *,
    model: str,
    prompt_name: str,
    title: str,
    question: str,
    markdown: str,
    signals: dict[str, Any],
    jury_scores: dict[str, float | None],
    config: Any,
    client_factory: ClientFactory | None,
    critic: DebatePoints | None = None,
) -> DebatePoints:
    prompt = _prompt(
        prompt_name,
        title=title,
        question=question,
        markdown=markdown[: int(getattr(config, "max_doc_chars", 11000))],
        signals_json=_json(signals),
        jury_json=_json(jury_scores),
        critic_json=_json(critic.model_dump(mode="json") if critic else {}),
        defender_json="{}",
        learning_outcomes="",
    )
    return complete_typed(
        StructuredPrompt(system=_SYSTEM, user=prompt),
        DebatePoints,
        client=_client(model, config, client_factory),
        retries=1,
        temperature=0.1,
        max_tokens=700,
    )


def _call_judge(
    *,
    model: str,
    title: str,
    question: str,
    signals: dict[str, Any],
    jury_scores: dict[str, float | None],
    critic: DebatePoints,
    defender: DebatePoints,
    config: Any,
    client_factory: ClientFactory | None,
) -> DebateJudgeOutput:
    prompt = _prompt(
        "didactic_debate_judge",
        title=title,
        question=question,
        markdown="",
        signals_json=_json(signals),
        jury_json=_json(jury_scores),
        critic_json=_json(critic.model_dump(mode="json")),
        defender_json=_json(defender.model_dump(mode="json")),
        learning_outcomes="",
    )
    return complete_typed(
        StructuredPrompt(system=_SYSTEM, user=prompt),
        DebateJudgeOutput,
        client=_client(model, config, client_factory),
        retries=1,
        temperature=0.1,
        max_tokens=500,
    )


def _fallback_debate(
    *,
    dimension: str,
    jury_scores: dict[str, float | None],
    signals: dict[str, Any],
    roles: dict[str, str],
) -> DebateResult:
    valid = {model: score for model, score in jury_scores.items() if score is not None}
    if not valid:
        score = 1.0
        strict = roles.get("critic", "critic")
        lenient = roles.get("defender", "defender")
    else:
        strict = min(valid, key=lambda model: valid[model] or 0.0)
        lenient = max(valid, key=lambda model: valid[model] or 0.0)
        score = round((float(valid[strict]) * 0.6 + float(valid[lenient]) * 0.4), 2)
    rationale = (
        "Fallback debate: structural signals and jury spread require human-readable review. "
        f"repetition_ratio={signals.get('repetition_ratio', 0)}, near_dup={signals.get('near_dup', 0)}."
    )
    return DebateResult(
        dimension=dimension,
        final_score=score,
        rationale=rationale,
        transcript=[
            DebateTurn(role="critic", model=strict, content=["Weak didactic evidence or low jury score."]),
            DebateTurn(role="defender", model=lenient, content=["Some formal requirements are present."]),
            DebateTurn(role="judge", model=roles.get("judge", "judge"), content=rationale),
        ],
    )


def _prompt(name: str, **values: Any) -> str:
    return load_prompt("checker", name, "v1").render(**values)


def _client(model: str, config: Any, client_factory: ClientFactory | None) -> Any:
    if client_factory is not None:
        return client_factory(model)
    return create_llm_client(provider=getattr(config, "provider", "polza"), model=model)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


_SYSTEM = "Return only valid JSON matching the requested schema."
