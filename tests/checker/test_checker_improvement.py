from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_checker_improvement_flow_extracts_generates_diff_and_downloads() -> None:
    client = TestClient(create_app())
    broken = "Без H1\n\nTODO\n\n```python\nprint('broken')"

    extracted = client.post("/checker/improve/extract", json={"readme_text": broken})
    assert extracted.status_code == 200, extracted.text
    extract_payload = extracted.json()
    assert extract_payload["request_id"]
    assert extract_payload["partial_seed"]["title_seed"]
    assert extract_payload["metadata"]["warnings"]

    generated = client.post(
        "/checker/improve/generate",
        json={
            "request_id": extract_payload["request_id"],
            "seed": {
                "title_seed": "Backend API",
                "project_description": "Собрать REST API и проверить его автотестами.",
                "learning_outcomes": ["Проектирует REST API", "Пишет pytest автотесты"],
                "required_tools": ["Python", "pytest"],
                "tasks_count": 2,
            },
        },
    )
    assert generated.status_code == 200, generated.text
    generation_id = generated.json()["generation_request_id"]

    status = client.get(f"/checker/improve/status/{generation_id}")
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "completed"
    assert "# Backend API" in payload["result"]["markdown"]
    assert "Критерии сдачи" in payload["result"]["markdown"]
    assert "didactic" in payload["result"]
    assert payload["result"]["didactic"]["overall_raw"] >= 1.0

    diff = client.get(f"/checker/improve/diff/{extract_payload['request_id']}")
    assert diff.status_code == 200
    assert diff.json()["stats"]["added"] > 0
    assert diff.json()["side_by_side"]

    download = client.get(f"/checker/improve/download/{generation_id}")
    assert download.status_code == 200
    assert "Backend API" in download.text


def test_checker_panel_exposes_legacy_improvement_controls_and_real_endpoints() -> None:
    client = TestClient(create_app())

    panel = client.get("/static/checker/panel.html")
    js = client.get("/static/checker/panel.js")

    assert panel.status_code == 200
    assert js.status_code == 200
    for control_id in (
        'id="readmeFile"',
        'id="learningOutcomes"',
        'id="checkerCurriculumFile"',
        'id="checkerCurriculumFileName"',
        'id="checkerScoreRing"',
        'id="checkerMetricsVersionSwitcher"',
        'id="checkerMetricsTabOriginal"',
        'id="checkerMetricsTabImproved"',
        'id="improvementModal"',
        'id="improveAddBlockExpander"',
        'id="improveNewBlockName"',
        'id="improveNewBlockCode"',
        'id="improveGroupSizeGroup"',
        'id="improveMethodologyHumanReview"',
        'id="improveBonusWishGroup"',
        'id="checkerRunRing"',
        'id="checkerRunPercent"',
        'id="checkerDiffTab"',
        'id="checkerDiffStats"',
        'id="checkerDiffTable"',
    ):
        assert control_id in panel.text
    for endpoint in (
        "/checker/evaluate",
        "/checker/improve/extract",
        "/checker/improve/generate",
        "/checker/improve/status/",
        "/checker/improve/diff/",
        "/checker/improve/download/",
        "learning_outcomes: lines(\"learningOutcomes\")",
        "result.didactic",
    ):
        assert endpoint in js.text
    for event_hook in (
        "handleCheckerCurriculumUpload",
        "switchCheckerMetricsVersion",
        "addImprovementThematicBlock",
        "toggleImproveGroupSize",
        "toggleImproveBonusWish",
    ):
        assert event_hook in js.text
