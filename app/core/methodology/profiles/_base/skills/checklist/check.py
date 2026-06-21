"""Checklist YAML/objectivity guard from regulation 3.3."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import yaml

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "checklist"


def _issue(code: str, message: str, evidence: dict[str, Any] | None = None) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", "hard", message, evidence or {})


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _matches_name(path: str | None, filenames: Iterable[str]) -> bool:
    if not path:
        return False
    name = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name in {item.lower() for item in filenames}


def _artifact_content(doc: GeneratedDoc, params: dict) -> str | None:
    for artifact in doc.artifacts:
        if artifact.kind == "checklist" or _matches_name(artifact.path, params["filenames"]):
            for key in params["content_metadata_keys"]:
                value = artifact.metadata.get(key)
                if isinstance(value, str) and value.strip():
                    return value
    return None


def _markdown_content(doc: GeneratedDoc, params: dict) -> str | None:
    markdown = doc.markdown or ""
    for filename in params["filenames"]:
        pattern = rf"{re.escape(filename)}\s*```(?:ya?ml)?\s*(.*?)```"
        if match := re.search(pattern, markdown, flags=re.IGNORECASE | re.DOTALL):
            return match.group(1).strip()
    if match := re.search(r"```(?:ya?ml)\s*(.*?)```", markdown, flags=re.IGNORECASE | re.DOTALL):
        return match.group(1).strip()
    return None


def _texts(node: Any, params: dict) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        title = None
        direct: list[str] = []
        for field in params["item_text_fields"]:
            value = node.get(field)
            if isinstance(value, str) and field == "title":
                title = value
            elif isinstance(value, str):
                direct.append(value)
        out.extend(direct or ([title] if title else []))
        for field in params["child_fields"]:
            if field in node:
                out.extend(_texts(node[field], params))
    elif isinstance(node, list):
        for item in node:
            out.extend(_texts(item, params))
    elif isinstance(node, str):
        out.append(node)
    return out


def _parse_yaml(raw: str) -> tuple[Any | None, RuleIssue | None]:
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return None, _issue("yaml_invalid", "check-list.yml должен быть валидным YAML.", {"error": str(exc)})
    if not isinstance(parsed, (dict, list)):
        return None, _issue("yaml_shape", "check-list.yml должен содержать YAML-объект или список пунктов.")
    return parsed, None


def _has_objective_marker(text: str, params: dict) -> bool:
    normalized = _norm(text)
    return any(str(marker).lower() in normalized for marker in params["objective_markers"]) or bool(re.search(r"\b\d+\b", text))


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    raw = _artifact_content(doc, params) or _markdown_content(doc, params)
    if not raw:
        return [_issue("missing", "Не найден check-list.yml с критериями проверки проекта.")]

    parsed, error = _parse_yaml(raw)
    if error:
        return [error]

    items = [text for text in _texts(parsed, params) if text.strip()]
    if not items:
        return [_issue("empty", "check-list.yml не содержит проверяемых пунктов.")]

    issues: list[RuleIssue] = []
    for text in items:
        normalized = _norm(text)
        vague = [term for term in params["vague_terms"] if str(term).lower() in normalized]
        if vague:
            issues.append(_issue("vague", "Пункт чек-листа содержит расплывчатую формулировку.", {"text": text, "terms": vague}))
        if not _has_objective_marker(text, params):
            issues.append(_issue("not_objective", "Пункт чек-листа не даёт однозначного ответа выполнено/нет.", {"text": text}))
    return issues
