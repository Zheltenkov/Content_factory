from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

from app.core import models
from app.core.models import (
    ArtifactRef,
    Competency,
    CompetencyEdge,
    CompetencyIndicator,
    EvidenceSource,
    GeneratedDoc,
    MethodologyContext,
    ProfilePackage,
    UPProject,
    UPSkeleton,
)
from app.core.methodology import rules


def test_competency_accepts_spravochnik_payload_and_round_trips() -> None:
    competency = Competency.model_validate(
        {
            "tmp_id": "tmp-1",
            "name": "Проектировать RAG-пайплайн",
            "source_name": "RAG design",
            "canonical_skill_id": 42,
            "canonical_group": "AI Systems",
            "indicators": [{"text": "Выбирает unit of evidence", "bloom": "analyze"}],
            "tools": ["PostgreSQL", "PostgreSQL", "FAISS"],
            "evidence_ids": ["ev-1"],
            "confidence": 0.8,
            "decision": "accepted",
        }
    )

    restored = Competency.model_validate_json(competency.model_dump_json())

    assert restored.competency_id == "tmp-1"
    assert restored.catalog_id == 42
    assert restored.group == "AI Systems"
    assert restored.status == "accepted"
    assert restored.bloom_level == "analyze"
    assert restored.tools == ["PostgreSQL", "FAISS"]
    assert "RAG design" in restored.aliases


def test_up_skeleton_normalizes_legacy_skill_strings_to_competency_refs() -> None:
    artifact = ArtifactRef(artifact_id="a1", family="practice", kind="markdown", path="README.md")
    project = UPProject.model_validate(
        {
            "block": "Блок 1",
            "block_goal": "Собрать базовый контур",
            "order": 1,
            "title": "RAG MVP",
            "outcomes_know": "chunking\nretrieval",
            "outcomes_can": ["настроить индекс"],
            "skills": ["Retrieval", "Evaluation"],
            "format": "индивидуальный",
            "artifacts": [artifact.model_dump()],
        }
    )
    skeleton = UPSkeleton(status="built", title="AI Engineer", rows=[project])
    restored = UPSkeleton.model_validate_json(skeleton.model_dump_json())

    assert restored.status == "built"
    assert restored.blocks[0].name == "Блок 1"
    assert restored.rows[0].competency_refs[0].canonical_name == "Retrieval"
    assert restored.rows[0].learning_outcomes == ["chunking", "retrieval", "настроить индекс"]
    assert restored.competency_ids() == ["Retrieval", "Evaluation"]


def test_profile_package_and_methodology_context_serialize_without_cycles() -> None:
    competency = Competency(
        competency_id="c1",
        catalog_id=7,
        canonical_name="Structured output validation",
        indicators=[CompetencyIndicator(text="Проверяет JSON schema", bloom="evaluate")],
        status="accepted",
    )
    package = ProfilePackage(
        profile_id="ai-base",
        title="AI Base",
        competencies=[competency],
        prerequisites=[CompetencyEdge(src="c1", dst="c2", relation_type="soft")],
        evidence_sources=[EvidenceSource(id="ev-1", source_type="framework", claim="Нужно валидировать вывод")],
    )
    context = MethodologyContext(
        run_id="run-1",
        profile=package,
        generated_doc=GeneratedDoc(markdown="# ok"),
        artifacts=[ArtifactRef(artifact_id="doc", family="readme", path="README.md")],
    ).with_value("curriculum.competency_weights", {"c1": 100})

    restored = MethodologyContext.model_validate_json(context.model_dump_json())

    assert restored.profile is not None
    assert restored.profile.competency_map()["c1"].canonical_name == "Structured output validation"
    assert restored.produced("curriculum.competency_weights") == {"c1": 100}


def test_methodology_rules_reexport_core_models() -> None:
    assert rules.GeneratedDoc is models.GeneratedDoc
    assert rules.RuleIssue is models.RuleIssue
    assert rules.DocImage("a.png", 400, 300, 50_000, "png").path == "a.png"
    assert rules.RuleIssue("visual", "visual.low", "soft", "msg").severity == "soft"


def test_core_models_import_without_cycles_and_do_not_define_skill_model() -> None:
    for module in pkgutil.iter_modules(models.__path__, prefix="app.core.models."):
        importlib.import_module(module.name)

    root = Path(__file__).resolve().parent.parent / "app" / "core" / "models"
    class_names: list[str] = []
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        class_names.extend(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

    assert "Competency" in class_names
    assert not [name for name in class_names if "Skill" in name]
