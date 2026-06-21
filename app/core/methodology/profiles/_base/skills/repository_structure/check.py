"""Repository inventory guard from regulation 3.5."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "repository_structure"


def _issue(code: str, message: str, evidence: dict[str, Any]) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", "hard", message, evidence)


def _norm(path: str) -> str:
    return path.replace("\\", "/").strip("/").lower()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, dict):
        return list(value)
    return [value]


def _inventory(doc: GeneratedDoc, params: dict) -> list[str]:
    paths: list[str] = []
    for key in params["inventory_metadata_keys"]:
        paths.extend(str(item) for item in _as_list(doc.metadata.get(key)) if str(item).strip())
    for artifact in doc.artifacts:
        if artifact.path and artifact.kind in params["inventory_kinds"]:
            paths.append(artifact.path)
        for key in params["inventory_metadata_keys"]:
            paths.extend(str(item) for item in _as_list(artifact.metadata.get(key)) if str(item).strip())
    return sorted({_norm(path) for path in paths})


def _has_path(paths: set[str], root: str, expected: str) -> bool:
    target = _norm(f"{root}/{expected}" if root else expected)
    return target in paths or any(path.startswith(f"{target}/") for path in paths)


def _root(paths: set[str], configured: str) -> str:
    configured = _norm(configured)
    if any(path == configured or path.startswith(f"{configured}/") for path in paths):
        return configured
    return ""


def _in_public_forbidden(path: str, public_root: str, forbidden: list[str]) -> str | None:
    if not public_root or not (path == public_root or path.startswith(f"{public_root}/")):
        return None
    tail = path[len(public_root) :].strip("/")
    segments = tail.split("/")
    for item in forbidden:
        expected = _norm(item)
        if expected in segments or tail == expected or tail.endswith(f"/{expected}"):
            return item
    return None


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    inventory = _inventory(doc, params)
    if not inventory:
        return []

    paths = set(inventory)
    protected_root = _root(paths, params["protected_root"])
    public_root = _root(paths, params["public_root"])
    issues: list[RuleIssue] = []

    for expected in [*params["required_files"], *params["required_hidden"]]:
        if not _has_path(paths, protected_root, expected):
            issues.append(
                _issue(
                    "required_missing",
                    "В защищённой части репозитория отсутствует обязательный файл или директория.",
                    {"root": protected_root or ".", "missing": expected},
                )
            )

    for path in inventory:
        if forbidden := _in_public_forbidden(path, public_root, params["forbidden_public"]):
            issues.append(
                _issue(
                    "for_forks_leak",
                    "В публичный for_forks не должны попадать автотесты или check-list.yml.",
                    {"path": path, "forbidden": forbidden},
                )
            )

    return issues
