from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import ArtifactRef, GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def _checklist_artifact() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="checklist",
        kind="checklist",
        family="practice",
        path="masters/check-list.yml",
        metadata={"content": "checks:\n  - criteria: Команда pytest запускается без ошибок\n"},
    )


def test_repository_structure_accepts_protected_and_public_inventory() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = GeneratedDoc(
        markdown="# Project",
        artifacts=[_checklist_artifact()],
        metadata={
            "repo_files": [
                "masters/README.md",
                "masters/LICENSE",
                "masters/.gitignore",
                "masters/.gitattributes",
                "masters/check-list.yml",
                "masters/tests/test_main.py",
                "masters/src/main.py",
                "for_forks/README.md",
                "for_forks/src/main.py",
                "for_forks/materials/setup.md",
            ]
        },
    )

    assert harness.validate("generator.evaluation", doc) == []


def test_repository_structure_flags_missing_required_files_and_for_forks_leaks() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = GeneratedDoc(
        markdown="# Project",
        artifacts=[_checklist_artifact()],
        metadata={
            "repo_files": [
                "masters/README.md",
                "masters/check-list.yml",
                "for_forks/README.md",
                "for_forks/check-list.yml",
                "for_forks/tests/test_main.py",
            ]
        },
    )

    issues = harness.validate("generator.evaluation", doc)
    codes = {issue.code for issue in issues}

    assert "repository_structure.required_missing" in codes
    assert "repository_structure.for_forks_leak" in codes


def test_repository_structure_ignores_documents_without_repo_inventory() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = GeneratedDoc(markdown="# Project", artifacts=[_checklist_artifact()])

    assert harness.validate("generator.evaluation", doc) == []
