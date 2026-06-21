from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import ArtifactRef, GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"
KIDS_SKILLS = ["program_types", "lesson_structure", "mentor_assets", "assessments", "student_portrait", "checklist"]


def _checklist(content: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="checklist",
        kind="checklist",
        family="practice",
        path="check-list.yml",
        metadata={"content": content},
    )


def _codes(skill_id: str, doc: GeneratedDoc, profile_id: str = "main") -> set[str]:
    profile = resolve_profile("kids", ROOT, program_type=profile_id)
    skill = profile.skills[skill_id]
    return {issue.code for issue in skill.check(doc, skill.params)}


def test_kids_resolves_all_program_types_and_overrides() -> None:
    expected = {
        "main": ("lesson_course", ["entry", "midterm", "final"], True),
        "intensive": ("lesson_course", ["final"], True),
        "master_class": ("lesson_single", [], False),
    }

    for program_type, (content_model, assessments, require_sjm) in expected.items():
        profile = resolve_profile("kids", ROOT, program_type=program_type)
        harness = Harness(profile)

        assert profile.content_model == content_model
        assert profile.skills["program_types"].params["kind"] == program_type
        assert profile.skills["assessments"].params["required"] == assessments
        assert profile.skills["student_portrait"].params["require_sjm"] is require_sjm
        assert "readme_structure" not in profile.skills
        assert profile.skills["checklist"].folder.parts[-3:] == ("kids", "skills", "checklist")
        assert harness.producers_bound_to("generator.") == []


def test_commerce_resolves_as_param_overlay_without_kids_skills() -> None:
    profile = resolve_profile("commerce", ROOT)

    assert profile.skills["readme_structure"].params["content_model"] == "readme_cyclic"
    assert profile.skills["readme_structure"].params["naming"] == "relaxed"
    assert profile.skills["voice"].params["formality"] == "detailed_peer"
    assert "program_types" not in profile.skills
    assert Harness(profile).producers_bound_to("generator.") == []


def test_kids_overlay_checks_accept_clean_main_program() -> None:
    doc = GeneratedDoc(
        markdown=(
            "# Программа\n\n"
            "Перечень учебных проектов и перечень занятий описаны для программы. "
            "К каждому занятию приложены презентация и методичка для наставника. "
            "Портрет наставника зафиксирован. Путь ученика и наставника описан как SJM."
        ),
        artifacts=[
            _checklist(
                """
checks:
  - criteria: Есть распределение ролей в команде
  - criteria: Есть минимум один критерий командной работы
  - criteria: Обратная связь содержит конкретный следующий шаг
"""
            )
        ],
        metadata={
            "program_type": "main",
            "content_model": "lesson_course",
            "lesson_hours": [2, 4],
            "project_span": [2, 4],
            "assessments": ["entry", "midterm", "final"],
            "mentor_portrait": "наставник помогает с затруднениями",
            "student_portrait": {
                "knowledge": ["знает базовые понятия"],
                "abilities": ["умеет собрать проект"],
                "soft_skills": ["коммуникация и командная работа"],
            },
            "sjm": "ключевые точки опыта и меры поддержки",
        },
    )

    for skill_id in KIDS_SKILLS:
        assert _codes(skill_id, doc) == set()


def test_kids_overlay_checks_flag_broken_main_program() -> None:
    doc = GeneratedDoc(
        markdown="# Проект\n\nНет структуры программы и материалов наставника.",
        artifacts=[
            _checklist(
                """
checks:
  - criteria: Проект оформлен аккуратно и понятно
"""
            )
        ],
        metadata={
            "program_type": "main",
            "content_model": "lesson_single",
            "lesson_hours": [6],
            "project_span": [1],
            "assessments": ["final"],
        },
    )

    codes = set()
    for skill_id in KIDS_SKILLS:
        codes |= _codes(skill_id, doc)

    assert {
        "program_types.content_model_mismatch",
        "program_types.structure_marker_missing",
        "lesson_structure.lesson_hours",
        "lesson_structure.project_span",
        "mentor_assets.missing_asset",
        "mentor_assets.mentor_portrait_missing",
        "assessments.missing",
        "student_portrait.portrait_part_missing",
        "student_portrait.sjm_missing",
        "checklist.vague",
        "checklist.not_objective",
        "checklist.missing_kids_topic",
    } <= codes


def test_master_class_skips_course_assessments_and_sjm() -> None:
    profile = resolve_profile("kids", ROOT, program_type="master_class")
    doc = GeneratedDoc(
        markdown=(
            "# Мастер-класс\n\n"
            "Один кейс ведёт ребёнка к практической задаче и показу результата. "
            "Портрет ученика: знает инструменты, умеет сделать мини-проект, тренирует коммуникацию."
        ),
        metadata={
            "program_type": "master_class",
            "content_model": "lesson_single",
            "duration_minutes": 90,
            "first_result_minutes": 15,
        },
    )

    assert profile.skills["assessments"].check(doc, profile.skills["assessments"].params) == []
    assert profile.skills["lesson_structure"].check(doc, profile.skills["lesson_structure"].params) == []
    assert profile.skills["student_portrait"].check(doc, profile.skills["student_portrait"].params) == []
