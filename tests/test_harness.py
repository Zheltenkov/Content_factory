"""Тесты harness: резолвинг профилей + маршрутизация по namespaced-стадиям + producer-инварианты."""
from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import DocImage, GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


# ===== 1. Резолвинг Дети: base + disables + overrides + adds + program_type + dotted-params =====
def test_kids_resolution():
    rp = resolve_profile("kids", ROOT, program_type="main")
    # disable
    assert "readme_structure" not in rp.skills
    # adds
    for a in ["program_types", "lesson_structure", "mentor_assets", "assessments", "student_portrait"]:
        assert a in rp.skills, f"добавленный скилл {a} потерян"
    # program_type -> content_model / artifact_target / family
    assert rp.content_model == "lesson_course"
    assert rp.artifact_target == "curriculum_plan"
    assert rp.artifact_family == "lesson"
    # terminology слой
    assert rp.terminology["branch"] == "программа"
    # override победил базовый voice
    assert rp.skills["voice"].params["formality"] == "warm_mentor"
    # profile.params (dotted) применился
    assert rp.skills["audience_level"].params["assumed_known"] == "none"
    # program_type.params (dotted) применился к нужным скиллам
    assert rp.skills["assessments"].params["required"] == ["entry", "midterm", "final"]
    assert rp.skills["lesson_structure"].params["lesson_hours"] == [2, 4]
    # базовый скилл, не тронутый оверлеем, на месте
    assert "visual_quality" in rp.skills


# ===== 2. master_class -> другая модель + свои params; readme-only скиллы отфильтрованы =====
def test_master_class_variant():
    rp = resolve_profile("kids", ROOT, program_type="master_class")
    assert rp.content_model == "lesson_single"
    assert rp.artifact_family == "lesson"
    assert rp.skills["lesson_structure"].params["duration_minutes"] == 90
    # document_integrity (applies_to: readme,lesson,guide) остаётся на lesson
    assert "document_integrity" in rp.skills


# ===== 3. Коммерция: циклическая модель — ОДИН параметр, без подмены папки =====
def test_commerce_cyclic_via_param():
    rp = resolve_profile("commerce", ROOT)
    assert rp.skills["readme_structure"].params["content_model"] == "readme_cyclic"
    assert rp.skills["readme_structure"].params["naming"] == "relaxed"
    assert rp.artifact_family == "readme"   # readme_structure не отфильтрован


# ===== 4. Producer невидим генератору; исполняется только на planner =====
def test_producer_routing():
    rp = resolve_profile("_base", ROOT)
    h = Harness(rp)
    # привязан к curriculum.planner
    planner = h.bind.get(("pre.stage", "curriculum.planner"), [])
    assert any(s.id == "competency_weights" for s in planner)
    # НЕ привязан ни к одной generator.*-стадии
    for (_hook, stage), sks in h.bind.items():
        if stage.startswith("generator."):
            assert all(s.id != "competency_weights" for s in sks), f"producer утёк в {stage}"
    # CI-инвариант: ни один producer не висит на generator.*
    assert h.producers_bound_to("generator.") == []
    # prepare на planner ПИШЕТ контекст; сумма весов == 100
    ctx = h.prepare("curriculum.planner", {"curriculum.projects": ["A", "B", "C", "D"]})
    assert "curriculum.competency_weights" in ctx
    assert sum(ctx["curriculum.competency_weights"].values()) == 100


# ===== 5. Harness реально гоняет augment + validate =====
def test_augment_and_validate_run():
    h = Harness(resolve_profile("_base", ROOT))
    # augment(generator.theory) включает voice с подставленным {{formality}}
    text = h.augment("generator.theory")
    assert "peer" in text, text
    # validate(generator.evaluation) гоняет реальный visual_quality.check -> ловит плохую картинку
    doc = GeneratedDoc(markdown="# x", images=[DocImage("a.png", 400, 300, 50_000, "png", dpi=120)])
    issues = h.validate("generator.evaluation", doc)
    assert any(i.code.startswith("visual_quality.") for i in issues), [i.code for i in issues]
    # на generator.theory валидаторов нет -> пусто
    assert h.validate("generator.theory", doc) == []


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            ok += 1
        except Exception:
            print(f"  FAIL  {t.__name__}")
            traceback.print_exc()
    print(f"\n{ok}/{len(tests)} passed")
