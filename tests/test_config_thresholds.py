from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.core.config import get_thresholds
from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import DocImage, GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_thresholds_yaml_is_single_source_for_structural_values() -> None:
    thresholds = get_thresholds()

    assert thresholds.get("structural.annotation_chars") == [220, 800]
    assert thresholds.get("structural.readability_band") == [45, 80]
    assert thresholds.get("structural.repetition_ratio_max") == 0.06
    assert thresholds.get("methodology.practice_tasks_range") == [2, 8]


def test_harness_injects_skill_thresholds_from_config() -> None:
    profile = resolve_profile("_base", ROOT)

    visual = profile.skills["visual_quality"]
    assert visual.params["min_resolution"] == [1200, 800]
    assert visual.params["min_dpi"] == 96
    assert visual.params["max_file_kb"] == 1024

    doc = GeneratedDoc(markdown="# x", images=[DocImage("bad.png", 400, 300, 50_000, "png", dpi=120)])
    issues = Harness(profile).validate("generator.evaluation", doc)
    assert any(issue.code == "visual_quality.resolution" for issue in issues)


def test_competency_weight_producer_reads_total_from_config() -> None:
    ctx = Harness(resolve_profile("_base", ROOT)).prepare(
        "curriculum.planner",
        {"curriculum.projects": ["A", "B", "C", "D"]},
    )

    assert sum(ctx["curriculum.competency_weights"].values()) == 100


def test_threshold_values_are_not_stored_in_skill_yaml_or_check_py() -> None:
    visual_yaml = yaml.safe_load((ROOT / "_base/skills/visual_quality/skill.yaml").read_text(encoding="utf-8"))
    weights_yaml = yaml.safe_load((ROOT / "_base/skills/competency_weights/skill.yaml").read_text(encoding="utf-8"))
    assert "params" not in visual_yaml
    assert "params" not in weights_yaml

    forbidden = re.compile(r"\b(1200|800|1000|96|1024|500|100)\b")
    for path in (ROOT / "_base/skills").glob("*/check.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path
