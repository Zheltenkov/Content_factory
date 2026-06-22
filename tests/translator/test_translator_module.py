from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.llm.client import LLMClient, LLMRequest, LLMResponse
from app.main import create_app
from app.modules.translator.router import get_translator_service
from app.modules.translator.service import TranslatorService


class MockTransport:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.responses.pop(0), model=request.model)


def client_with(*responses: str) -> tuple[TestClient, MockTransport]:
    transport = MockTransport(*responses)
    llm = LLMClient(model="gpt-4o-mini", provider="mock", transport=transport)
    service = TranslatorService(client_factory=lambda **_kwargs: llm)
    app = create_app()
    app.dependency_overrides[get_translator_service] = lambda: service
    return TestClient(app), transport


def test_readme_translation_preserves_protected_code_block() -> None:
    client, transport = client_with(
        "# REST API\n\nTranslated intro for learners.\n\n[[[BLOCK_0]]]",
    )
    markdown = "# REST API\n\nОписание проекта для студентов.\n\n```python\nprint('ok')\n```"

    started = client.post(
        "/translator/translate/readme",
        json={"markdown": markdown, "target_language": "en", "translation_mode": "literal"},
    )
    assert started.status_code == 200
    request_id = started.json()["request_id"]

    status = client.get(f"/translator/translate/status/{request_id}")
    payload = status.json()

    assert status.status_code == 200
    assert payload["status"] == "completed"
    assert "Translated intro" in payload["translated_markdown"]
    assert "```python\nprint('ok')\n```" in payload["translated_markdown"]
    assert transport.requests
    assert "PROTECTED_BLOCK" in transport.requests[0].user


def test_video_translation_builds_subtitle_artifacts() -> None:
    client, _transport = client_with('{"segments":[{"id":1,"text":"Hello from lesson"}]}')
    files = {"file": ("lesson.srt", b"1\n00:00:00,000 --> 00:00:04,000\n\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82\n", "text/plain")}

    started = client.post(
        "/translator/translate/video",
        data={"target_language": "en", "output_mode": "subtitles_only"},
        files=files,
    )
    assert started.status_code == 200
    request_id = started.json()["request_id"]

    status = client.get(f"/translator/translate/status/{request_id}").json()
    assert status["job_type"] == "video"
    assert status["status"] == "completed"
    assert "Hello from lesson" in status["translated_subtitles"]
    assert sorted(status["result_links"]) == ["ass", "srt", "transcript", "vtt"]

    srt = client.get(f"/translator/translate/download/{request_id}?type=srt")
    assert srt.status_code == 200
    assert "Hello from lesson" in srt.text


def test_document_upload_translation_returns_source_metadata() -> None:
    client, _transport = client_with("# Uploaded lesson\n\nTranslated body.")
    files = {"file": ("lesson.md", b"# Lesson\n\n\xd0\xa0\xd1\x83\xd1\x81\xd1\x81\xd0\xba\xd0\xb8\xd0\xb9 \xd1\x82\xd0\xb5\xd0\xba\xd1\x81\xd1\x82.", "text/markdown")}

    started = client.post(
        "/translator/translate/document",
        data={"target_language": "en", "translation_mode": "literal"},
        files=files,
    )

    assert started.status_code == 200
    status = client.get(f"/translator/translate/status/{started.json()['request_id']}").json()
    assert status["status"] == "completed"
    assert status["source_filename"] == "lesson.md"
    assert status["source_format"] == "md"
    assert "Translated body" in status["translated_markdown"]


def test_video_translation_reports_deferred_burned_video_adapter() -> None:
    client, _transport = client_with('{"segments":[{"id":1,"text":"Hello with subtitles"}]}')
    files = {"file": ("lesson.srt", b"1\n00:00:00,000 --> 00:00:04,000\n\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82\n", "text/plain")}

    started = client.post(
        "/translator/translate/video",
        data={"target_language": "en", "output_mode": "both", "subtitle_style": "outline"},
        files=files,
    )

    assert started.status_code == 200
    status = client.get(f"/translator/translate/status/{started.json()['request_id']}").json()
    assert status["status"] == "completed"
    assert status["error_code"] == "video_burn_deferred"
    assert sorted(status["result_links"]) == ["ass", "srt", "transcript", "vtt"]


def test_translator_manifest_and_panel_are_registered() -> None:
    client, _transport = client_with("# Title\n\nTranslated text.")

    modules = client.get("/api/modules").json()
    translator = next(item for item in modules if item["id"] == "translator")

    assert translator["ui_panel"] == "translator/panel.html"
    assert translator["dashboard_tile"]["subtitle"] == "Перевод документов и видео"
    assert client.get("/static/translator/panel.html").status_code == 200


def test_translator_panel_uses_real_backend_contracts() -> None:
    client, _transport = client_with("# Title\n\nTranslated text.")

    panel = client.get("/static/translator/panel.html")
    js = client.get("/static/translator/panel.js")

    assert panel.status_code == 200
    assert js.status_code == 200
    assert 'id="translatorSubtitleStyle"' in panel.text
    assert 'data-tab-target="translatorJobTab"' in panel.text
    assert '<script src="/static/shared/shell.js"></script>' in panel.text
    assert '<script src="/static/shared/markdown.js"></script>' in panel.text
    assert 'fetch("/translator/translate/document"' in js.text
    assert 'fetch("/translator/translate/readme"' in js.text
    assert 'fetch("/translator/translate/video"' in js.text
    assert "translator/translate/status" in js.text
    assert "translator/translate/download" in js.text
    assert "mock" not in js.text.lower()
