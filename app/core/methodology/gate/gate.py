"""Compact deterministic MethodologyGate port."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from typing import Any

from app.core.config import get_thresholds
from app.core.methodology.gate.models import IssueSeverity, ReviewStatus, StageReviewIssue, StageReviewResult
from app.core.models import MethodologyContext, RuleIssue


class MethodologyGate:
    """Review workflow stages with deterministic contracts and no module imports."""

    reviewed_stages = {
        "context",
        "task_planning",
        "skeleton",
        "theory",
        "practice",
        "dataset_generation",
        "evaluation",
        "finalize",
    }

    def review(self, stage: str, context: MethodologyContext | dict[str, Any]) -> StageReviewResult:
        """Run stage checks and return a typed review result."""
        start = time.perf_counter()
        payload = _context_dict(context)
        issues: list[StageReviewIssue] = []
        metrics: dict[str, Any] = {}
        evidence: dict[str, Any] = {}
        if stage not in self.reviewed_stages:
            return StageReviewResult(stage=stage, status="skipped", duration_ms=_elapsed_ms(start))

        reviewer = getattr(self, f"_review_{stage}", self._review_default)
        reviewer(payload, issues, metrics, evidence)
        status = self._status_from_issues(issues)
        return StageReviewResult(
            stage=stage,
            status=status,
            issues=issues,
            repair_instructions=[
                issue.repair_hint for issue in issues if issue.repair_hint and issue.severity in {"major", "critical"}
            ],
            human_review_required=any(issue.severity == "critical" for issue in issues),
            metrics=metrics,
            evidence=evidence,
            duration_ms=_elapsed_ms(start),
        )

    def _review_context(
        self,
        context: dict[str, Any],
        issues: list[StageReviewIssue],
        metrics: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        seed = context.get("seed") or context.get("current_project")
        profile = context.get("profile")
        up = context.get("up")
        outcomes = _list_value(seed, "learning_outcomes") or _list_value(seed, "outcomes_can")
        competencies = _list_value(seed, "competency_refs") or _list_value(seed, "skills")
        metrics.update(
            {
                "has_seed": seed is not None,
                "has_profile": profile is not None,
                "has_up": up is not None,
                "learning_outcomes_count": len(outcomes),
                "competencies_count": len(competencies),
            }
        )
        if seed is None:
            self._add_issue(issues, "context.seed_missing", "Project seed/current project is missing.", "critical")
            return
        if not outcomes:
            self._add_issue(
                issues,
                "context.learning_outcomes_empty",
                "Learning outcomes are empty.",
                "critical",
                "Fill project learning outcomes before generation or route the task to human review.",
            )
        if not competencies:
            self._add_issue(
                issues,
                "context.competencies_empty",
                "Project competencies are empty.",
                "major",
                "Attach at least one competency_ref from the curriculum/profile package.",
            )
        evidence["project_title"] = _get(seed, "title")

    def _review_task_planning(
        self,
        context: dict[str, Any],
        issues: list[StageReviewIssue],
        metrics: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        task_plan = context.get("task_plan")
        if task_plan is None:
            self._add_issue(issues, "task_planning.plan_missing", "Task plan is missing.", "major")
            return
        tasks_count = int(_get(task_plan, "tasks_count", 0) or 0)
        min_tasks, max_tasks = get_thresholds().require_range("methodology.practice_tasks_range")
        metrics["tasks_count"] = tasks_count
        if tasks_count < min_tasks or tasks_count > max_tasks:
            self._add_issue(
                issues,
                "task_planning.tasks_count_out_of_range",
                f"Task count is outside supported range {min_tasks}-{max_tasks}.",
                "major",
                f"Regenerate the task plan with {min_tasks}-{max_tasks} practice tasks.",
                {"actual": tasks_count, "min": min_tasks, "max": max_tasks},
            )
        evidence["complexity"] = _get(task_plan, "complexity")

    def _review_skeleton(self, context: dict[str, Any], issues: list[StageReviewIssue], metrics: dict[str, Any], _: dict[str, Any]) -> None:
        markdown = str(context.get("markdown") or "")
        metrics["markdown_chars"] = len(markdown)
        if not markdown.strip():
            self._add_issue(issues, "skeleton.markdown_empty", "Skeleton markdown is empty.", "critical")
        for chapter in ("1", "2", "3"):
            if not _extract_chapter(markdown, chapter, str(int(chapter) + 1) if chapter != "3" else None):
                self._add_issue(issues, f"skeleton.chapter_{chapter}_missing", f"Chapter {chapter} is missing.", "major")

    def _review_theory(self, context: dict[str, Any], issues: list[StageReviewIssue], metrics: dict[str, Any], _: dict[str, Any]) -> None:
        markdown = str(context.get("markdown") or "")
        chapter = _extract_chapter(markdown, "2", "3")
        metrics["theory_words"] = _count_words(chapter)
        metrics["theory_parts_count"] = len(context.get("theory_parts") or [])
        if not chapter:
            self._add_issue(issues, "theory.chapter_missing", "Chapter 2 is missing or empty.", "critical")
            return
        if not context.get("theory_parts"):
            self._add_issue(issues, "theory.parts_missing", "Structured theory_parts are missing.", "major")
        if re.search(r"\b(освоил репозиторий|P2P|peer-to-peer)\b", chapter, re.I):
            self._add_issue(issues, "theory.static_instruction_leak", "Static legacy instruction leaked into theory.", "major")

    def _review_practice(
        self,
        context: dict[str, Any],
        issues: list[StageReviewIssue],
        metrics: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        markdown = str(context.get("markdown") or "")
        tasks = list(context.get("practice_tasks") or [])
        expected = _get(context.get("task_plan"), "tasks_count")
        chapter = _extract_chapter(markdown, "3", None)
        metrics.update({"practice_tasks_count": len(tasks), "expected_tasks_count": expected})
        evidence["practice_titles"] = [_get(task, "title", "") for task in tasks[:8]]
        if not chapter:
            self._add_issue(issues, "practice.chapter_missing", "Chapter 3 is missing or empty.", "critical")
            return
        if not tasks:
            self._add_issue(issues, "practice.tasks_missing", "Structured practice_tasks are missing.", "major")
        if expected is not None and len(tasks) != int(expected):
            self._add_issue(
                issues,
                "practice.tasks_count_mismatch",
                "Practice task count does not match TaskPlan.",
                "major",
                "Repair practice section to match the planned task count.",
                {"expected": expected, "actual": len(tasks)},
            )
        self._review_practice_materials(tasks, issues, evidence)

    def _review_dataset_generation(
        self,
        context: dict[str, Any],
        issues: list[StageReviewIssue],
        metrics: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        tasks = list(context.get("practice_tasks") or [])
        dataset_files = list(context.get("dataset_files") or [])
        evidence_specs = list(context.get("evidence_specs") or [])
        expected_refs = sorted({ref for task in tasks for ref in _material_refs(_get(task, "input_data", ""))})
        file_paths = {_norm_path(_get(file, "path", "")) for file in dataset_files if isinstance(file, dict)}
        spec_paths = {_norm_path(_evidence_spec_path(spec)) for spec in evidence_specs}
        missing_files = [ref for ref in expected_refs if _norm_path(ref) not in file_paths]
        missing_specs = [ref for ref in expected_refs if _norm_path(ref) not in spec_paths]
        metrics.update(
            {
                "material_refs_count": len(expected_refs),
                "dataset_files_count": len(dataset_files),
                "evidence_specs_count": len(evidence_specs),
                "missing_dataset_files_count": len(missing_files),
                "missing_evidence_specs_count": len(missing_specs),
            }
        )
        evidence.update({"material_refs": expected_refs, "dataset_file_paths": sorted(file_paths), "evidence_spec_paths": sorted(spec_paths)})
        if missing_files:
            self._add_issue(issues, "dataset_generation.files_missing", "Dataset files are missing for referenced materials.", "major", details={"paths": missing_files})
        if missing_specs:
            self._add_issue(issues, "dataset_generation.evidence_specs_missing", "Evidence specs are missing for referenced materials.", "major", details={"paths": missing_specs})
        for spec in evidence_specs:
            if _evidence_spec_path(spec) and not all(_evidence_spec_list(spec, key) for key in ("contains", "excludes", "student_must_derive")):
                self._add_issue(issues, "dataset_generation.evidence_spec_weak", "Evidence spec lacks raw-data contract fields.", "minor", details={"path": _evidence_spec_path(spec)})

    def _review_evaluation(
        self,
        context: dict[str, Any],
        issues: list[StageReviewIssue],
        metrics: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        rubric = context.get("rubric_json")
        didactic = context.get("didactic_json")
        metrics["has_rubric"] = isinstance(rubric, dict) and bool(rubric)
        if not isinstance(rubric, dict) or not rubric:
            self._add_issue(
                issues,
                "evaluation.rubric_missing",
                "Rubric result is missing.",
                "critical",
                "Run final structural/didactic evaluation before finalization.",
            )
            return

        rubric_issues = list(_iter_rubric_issues(rubric))
        severity_counts: dict[str, int] = {"hard": 0, "soft": 0, "critical": 0, "major": 0, "minor": 0}
        for item in rubric_issues:
            severity = _rubric_severity(item)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            if severity in {"hard", "critical"}:
                self._add_issue(
                    issues,
                    str(item.get("code") or "evaluation.hard_issue"),
                    str(item.get("message") or "Structural hard issue failed."),
                    "critical",
                    "Route the artifact to repair or human review before finalization.",
                    item,
                )
            elif severity in {"soft", "major"}:
                self._add_issue(
                    issues,
                    str(item.get("code") or "evaluation.soft_issue"),
                    str(item.get("message") or "Evaluation warning."),
                    "major" if severity == "major" else "minor",
                    details=item,
                )

        didactic_needs_review = bool(_get(didactic, "needs_human_review", False))
        if didactic_needs_review:
            self._add_issue(
                issues,
                "evaluation.didactic_needs_human_review",
                "Didactic evaluator requested human review.",
                "critical",
                "Review didactic judge report before accepting the artifact.",
                {"didactic_json": didactic},
            )

        metrics.update(
            {
                "rubric_keys": sorted(rubric.keys())[:30],
                "rubric_issues_count": len(rubric_issues),
                "rubric_hard_count": severity_counts.get("hard", 0) + severity_counts.get("critical", 0),
                "rubric_soft_count": severity_counts.get("soft", 0) + severity_counts.get("minor", 0) + severity_counts.get("major", 0),
                "didactic_needs_human_review": didactic_needs_review,
            }
        )
        evidence["rubric_summary"] = _rubric_summary(rubric)
        if didactic is not None:
            evidence["didactic_summary"] = _didactic_summary(didactic)

    def _review_finalize(self, context: dict[str, Any], issues: list[StageReviewIssue], metrics: dict[str, Any], evidence: dict[str, Any]) -> None:
        result = context.get("result")
        markdown = str(context.get("markdown") or "")
        report_json = _get(result, "report_json") if result is not None else context.get("report_json")
        metrics.update({"has_result": result is not None, "markdown_chars": len(markdown), "has_report_json": isinstance(report_json, dict)})
        if result is None:
            self._add_issue(issues, "finalize.result_missing", "OrchestratorResult is missing.", "critical")
        if not markdown.strip():
            self._add_issue(issues, "finalize.markdown_missing", "Final markdown is missing.", "critical")
        if not isinstance(report_json, dict):
            self._add_issue(issues, "finalize.report_missing", "report_json is missing.", "critical")
        else:
            evidence["report_keys"] = sorted(report_json.keys())[:30]

    def _review_default(self, *_: Any) -> None:
        return

    def _review_practice_materials(self, tasks: list[Any], issues: list[StageReviewIssue], evidence: dict[str, Any]) -> None:
        solution_refs: dict[int, list[str]] = {}
        non_raw: dict[int, list[str]] = {}
        dependency_gaps: list[dict[str, str]] = []
        for idx, task in enumerate(tasks, 1):
            text = str(_get(task, "input_data", "") or "")
            refs = _solution_like_refs(text)
            if refs:
                solution_refs[idx] = refs
            phrase_issues = _non_raw_material_issues(text)
            if phrase_issues:
                non_raw[idx] = phrase_issues
            if idx > 1:
                previous_artifact = str(_get(tasks[idx - 2], "artifact_location", "") or "")
                if previous_artifact and previous_artifact not in text:
                    dependency_gaps.append({"task": str(idx), "previous_artifact": previous_artifact})
        if solution_refs:
            self._add_issue(issues, "practice.solution_materials_leak", "Practice input references solution-like materials.", "major", details={"refs": solution_refs})
        if non_raw:
            self._add_issue(issues, "practice.non_raw_input_materials", "Practice input contains processed-material phrases.", "major", details={"tasks": non_raw})
        if dependency_gaps:
            self._add_issue(issues, "practice.task_dependency_missing", "Practice tasks do not consume previous task artifacts.", "major", details={"gaps": dependency_gaps})
        evidence["solution_material_refs"] = solution_refs
        evidence["dependency_gaps"] = dependency_gaps

    @staticmethod
    def _add_issue(
        issues: list[StageReviewIssue],
        code: str,
        message: str,
        severity: IssueSeverity,
        repair_hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        issues.append(StageReviewIssue(code=code, message=message, severity=severity, repair_hint=repair_hint, details=details or {}))

    @staticmethod
    def _status_from_issues(issues: list[StageReviewIssue]) -> ReviewStatus:
        if not issues:
            return "passed"
        if any(issue.severity == "critical" for issue in issues):
            return "failed"
        return "warning"


def _context_dict(context: MethodologyContext | dict[str, Any]) -> dict[str, Any]:
    if isinstance(context, MethodologyContext):
        return {
            "profile": context.profile,
            "up": context.up,
            "current_project": context.current_project,
            "generated_doc": context.generated_doc,
            "artifacts": context.artifacts,
            **context.values,
            **context.metadata,
        }
    return dict(context)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _list_value(obj: Any, key: str) -> list[Any]:
    value = _get(obj, key, [])
    return value if isinstance(value, list) else []


def _extract_chapter(markdown: str, chapter_number: str, next_chapter_number: str | None) -> str:
    next_pattern = rf"\n##\s+Глава\s+{next_chapter_number}\b" if next_chapter_number else r"\Z"
    match = re.search(rf"##\s+Глава\s+{chapter_number}[^\n]*\n(.*?)(?={next_pattern})", markdown, re.S)
    return match.group(1).strip() if match else ""


def _count_words(text: str) -> int:
    return len(re.findall(r"\b[\wА-Яа-яЁё-]+\b", text))


def _material_refs(text: str) -> list[str]:
    return re.findall(r"`([^`]+\.(?:md|csv|json|txt|xlsx|docx))`", str(text), flags=re.I)


def _solution_like_refs(text: str) -> list[str]:
    refs = []
    for ref in _material_refs(text):
        if re.search(r"(final|solution|answer|result|готов|решени|отчет|отчёт)", ref, re.I) or re.search(r"(готовый|классификац|решени|вывод)", text, re.I):
            refs.append(ref)
    return refs


def _non_raw_material_issues(text: str) -> list[str]:
    patterns = [r"готов[а-я]*\s+отч[её]т", r"готов[а-я]*\s+реестр", r"с классификац", r"готов[а-я]*\s+вывод", r"финальн[а-я]*\s+решени"]
    return [pattern for pattern in patterns if re.search(pattern, text, re.I)]


def _norm_path(path: str) -> str:
    return path.replace("\\", "/").strip().lower()


def _evidence_spec_path(spec: Any) -> str:
    return str(_get(spec, "path", "") or "")


def _evidence_spec_list(spec: Any, key: str) -> list[Any]:
    value = _get(spec, key, [])
    return value if isinstance(value, list) else []


def _iter_rubric_issues(rubric: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("issues", "rule_issues", "structural_issues"):
        yield from _coerce_issue_list(rubric.get(key))
    for item in _coerce_issue_list(rubric.get("items")):
        if _is_failed_item(item):
            yield item
    for value in rubric.values():
        if isinstance(value, dict):
            yield from _iter_rubric_issues(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _is_failed_item(item):
                    yield item


def _coerce_issue_list(value: Any) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else []
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, RuleIssue):
            out.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            out.append(dict(item))
        elif hasattr(item, "model_dump"):
            out.append(item.model_dump(mode="json"))
    return out


def _is_failed_item(item: dict[str, Any]) -> bool:
    if item.get("passed") is False or item.get("ok") is False:
        return True
    status = str(item.get("status") or item.get("result") or "").lower()
    return status in {"failed", "fail", "error", "critical", "hard"}


def _rubric_severity(item: dict[str, Any]) -> str:
    raw = str(item.get("severity") or item.get("level") or "").lower()
    if raw in {"hard", "critical"}:
        return raw
    if raw in {"soft", "major", "minor", "info"}:
        return raw
    return "hard" if _is_failed_item(item) and item.get("hard", False) else "soft"


def _rubric_summary(rubric: dict[str, Any]) -> dict[str, Any]:
    return {key: rubric.get(key) for key in ("score", "total", "max_score", "passed", "failed") if key in rubric}


def _didactic_summary(didactic: Any) -> dict[str, Any]:
    if not isinstance(didactic, dict):
        return {"value": str(didactic)}
    return {
        key: didactic.get(key)
        for key in ("overall", "overall_calibrated", "confidence", "needs_human_review")
        if key in didactic
    }


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)
