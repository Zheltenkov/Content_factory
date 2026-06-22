from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.llm.client import LLMClient, LLMRequest, LLMResponse
from app.modules.checker.didactic.jury import DidacticJuryConfig, DimensionSpec, evaluate_didactic


class QueueTransport:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.responses.pop(0), model=request.model)


def _config(*, debate_on_escalate: bool = False) -> DidacticJuryConfig:
    return DidacticJuryConfig(
        generator_model="qwen/generator",
        jury_models=["qwen/generator", "anthropic/claude", "openai/gpt", "google/gemini"],
        debate_roles={"critic": "deepseek/critic", "defender": "qwen/defender", "judge": "google/judge"},
        debate_on_escalate=debate_on_escalate,
        dimensions={"coherence": DimensionSpec(title="Связность", question="Есть ли единый маршрут?")},
    )


def _factory(transports: dict[str, QueueTransport], requested: list[str]):
    def make(model: str) -> LLMClient:
        requested.append(model)
        return LLMClient(model=model, provider="mock", transport=transports[model])

    return make


def test_poll_jury_uses_median_of_three_models_and_excludes_generator() -> None:
    transports = {
        "anthropic/claude": QueueTransport('{"score": 3, "rationale": "strict", "evidence": ["a"], "abstain": false}'),
        "openai/gpt": QueueTransport('{"score": 5, "rationale": "lenient", "evidence": ["b"], "abstain": false}'),
        "google/gemini": QueueTransport('{"score": 4, "rationale": "middle", "evidence": ["c"], "abstain": false}'),
    }
    requested: list[str] = []

    report = evaluate_didactic(
        "# README\n\n## Глава 1\n\nText.",
        config=_config(),
        signals={"repetition_ratio": 0, "near_dup": 0, "broken_tables": 0, "diagram_match_avg": 1, "example_count": 3},
        client_factory=_factory(transports, requested),
    )

    assert report.jury == ["anthropic/claude", "openai/gpt", "google/gemini"]
    assert "qwen/generator" not in requested
    assert requested == report.jury
    assert report.dimensions[0].score == 4.0
    assert report.overall_raw == 4.0
    assert report.needs_human_review is False


def test_abstain_escalates_to_human_review() -> None:
    transports = {
        "anthropic/claude": QueueTransport('{"score": 4, "rationale": "ok", "evidence": [], "abstain": false}'),
        "openai/gpt": QueueTransport('{"score": null, "rationale": "not enough", "evidence": [], "abstain": true}'),
        "google/gemini": QueueTransport('{"score": 4, "rationale": "ok", "evidence": [], "abstain": false}'),
    }
    requested: list[str] = []

    report = evaluate_didactic(
        "# README",
        config=_config(),
        signals={"repetition_ratio": 0, "near_dup": 0, "broken_tables": 0, "diagram_match_avg": 1, "example_count": 1},
        client_factory=_factory(transports, requested),
    )

    assert report.dimensions[0].score == 4.0
    assert report.dimensions[0].abstained_models == ["openai/gpt"]
    assert report.dimensions[0].human_review_required is True
    assert report.needs_human_review is True
    assert "abstain:coherence:openai/gpt" in report.abstain_reasons


def test_low_score_runs_debate_on_distinct_role_models() -> None:
    transports = {
        "anthropic/claude": QueueTransport('{"score": 2, "rationale": "weak", "evidence": ["a"], "abstain": false}'),
        "openai/gpt": QueueTransport('{"score": 2, "rationale": "weak", "evidence": ["b"], "abstain": false}'),
        "google/gemini": QueueTransport('{"score": 2, "rationale": "weak", "evidence": ["c"], "abstain": false}'),
        "deepseek/critic": QueueTransport('{"points": ["practice is disconnected"]}'),
        "qwen/defender": QueueTransport('{"points": ["basic structure exists"]}'),
        "google/judge": QueueTransport('{"score": 2.4, "rationale": "critic wins"}'),
    }
    requested: list[str] = []

    report = evaluate_didactic(
        "# README",
        config=_config(debate_on_escalate=True),
        signals={"repetition_ratio": 0.2, "near_dup": 7, "broken_tables": 0, "diagram_match_avg": 1, "example_count": 0},
        client_factory=_factory(transports, requested),
    )

    score = report.dimensions[0]
    assert score.escalated is True
    assert score.score == 2.4
    assert [turn["role"] for turn in score.debate_transcript] == ["critic", "defender", "judge"]
    assert requested[-3:] == ["deepseek/critic", "qwen/defender", "google/judge"]
    assert report.needs_human_review is True


def test_debate_roles_must_be_distinct_and_not_generator() -> None:
    with pytest.raises(ValidationError, match="different models"):
        DidacticJuryConfig(
            generator_model="qwen/generator",
            jury_models=["anthropic/claude", "openai/gpt", "google/gemini"],
            debate_roles={"critic": "deepseek/critic", "defender": "deepseek/critic", "judge": "google/judge"},
            dimensions={"coherence": DimensionSpec(title="Связность", question="Есть ли единый маршрут?")},
        )
