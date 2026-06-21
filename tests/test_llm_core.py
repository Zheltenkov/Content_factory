from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.core.llm.client import LLMRequest, LLMResponse, LLMClient, TokenUsage
from app.core.llm.observe import LLMTraceRecorder, ObservedLLMClient
from app.core.llm.prompt_loader import load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed


class TypedPayload(BaseModel):
    title: str
    score: int


class MockTransport:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        content = self.responses.pop(0)
        return LLMResponse(
            content=content,
            model=request.model,
            tokens=TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        )


def test_complete_typed_returns_pydantic_model_on_mock_llm() -> None:
    transport = MockTransport('{"title": "ok", "score": 7}')
    client = LLMClient(model="gpt-4o-mini", provider="mock", transport=transport)

    result = complete_typed("Return payload", TypedPayload, client=client)

    assert result == TypedPayload(title="ok", score=7)
    response_format = transport.requests[0].response_format
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "TypedPayload"


def test_complete_typed_repairs_invalid_first_response() -> None:
    transport = MockTransport("not-json", '```json\n{"title": "fixed", "score": 9}\n```')
    client = LLMClient(model="gpt-4o-mini", provider="mock", transport=transport)

    result = complete_typed(
        StructuredPrompt(system="Return JSON", user="Return payload"),
        TypedPayload,
        client=client,
        retries=1,
    )

    assert result.title == "fixed"
    assert len(transport.requests) == 2
    assert "Previous response failed schema validation" in transport.requests[1].user


def test_observed_client_records_run_stage_model_and_tokens() -> None:
    transport = MockTransport('{"title": "ok", "score": 7}')
    raw_client = LLMClient(model="gpt-4o-mini", provider="mock", transport=transport)
    recorder = LLMTraceRecorder()
    client = ObservedLLMClient(raw_client, recorder, run_id="run-1", stage="generator.theory")

    assert client.complete(system="s", user="u", response_format="json_object") == '{"title": "ok", "score": 7}'

    event = recorder.events[0]
    assert event["run_id"] == "run-1"
    assert event["stage"] == "generator.theory"
    assert event["model"] == "gpt-4o-mini"
    assert event["tokens"]["total_tokens"] == 5
    assert event["schema"] == "json_object"
    assert event["status"] == "success"
    assert event["input_hash"]


def test_prompt_loader_loads_versioned_markdown() -> None:
    root = Path(__file__).resolve().parent / "fixtures" / "prompts"

    template = load_prompt("generator", "title", "v1", root=root)

    assert template.render(topic="AI").strip() == "Title for AI"
    assert template.prompt_hash


def test_complete_typed_uses_json_object_for_non_schema_models() -> None:
    transport = MockTransport('{"title": "ok", "score": 1}')
    client = LLMClient(model="gpt-3.5-turbo", provider="mock", transport=transport)

    complete_typed({"system": "s", "user": "u"}, TypedPayload, client=client)

    assert transport.requests[0].response_format == "json_object"
