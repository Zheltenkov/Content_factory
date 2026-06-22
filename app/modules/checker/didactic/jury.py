"""C3 didactic axis: PoLL jury with model diversity and abstain escalation."""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from collections.abc import Callable
from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import get_thresholds
from app.core.llm import StructuredPrompt, complete_typed, load_prompt
from app.core.llm.client import create_llm_client
from app.modules.checker.didactic.debate import DebateResult, run_debate

ClientFactory = Callable[[str], Any]


class DidacticConfigError(ValueError):
    """Raised when D4 model-selection constraints are not satisfied."""


class DimensionSpec(BaseModel):
    """One didactic quality dimension from the notebook."""

    model_config = ConfigDict(extra="forbid")

    title: str
    question: str


class JurorVerdict(BaseModel):
    """Structured verdict from one jury model."""

    model_config = ConfigDict(extra="forbid")

    score: float | None = None
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    abstain: bool = False

    @field_validator("score")
    @classmethod
    def _score_range(cls, value: float | None) -> float | None:
        return None if value is None else max(1.0, min(5.0, float(value)))

    @model_validator(mode="after")
    def _score_or_abstain(self) -> "JurorVerdict":
        if self.score is None:
            self.abstain = True
        return self


class DidacticDimensionScore(BaseModel):
    """Aggregated PoLL result for one dimension."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    title: str
    score: float
    confidence: float
    per_model: dict[str, float | None] = Field(default_factory=dict)
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    abstained_models: list[str] = Field(default_factory=list)
    escalated: bool = False
    escalate_reason: str = ""
    debate_transcript: list[dict[str, Any]] = Field(default_factory=list)
    human_review_required: bool = False


class DidacticQualityReport(BaseModel):
    """Didactic-axis JSON consumed separately from structural rubric_json."""

    model_config = ConfigDict(extra="forbid")

    dimensions: list[DidacticDimensionScore]
    overall_raw: float
    overall_calibrated: float | None = None
    calibrated: bool = False
    needs_human_review: bool = False
    abstain_reasons: list[str] = Field(default_factory=list)
    jury: list[str] = Field(default_factory=list)
    n_jury: int = 0
    generator_model: str
    config_warnings: list[str] = Field(default_factory=list)


class DidacticJuryConfig(BaseModel):
    """Config pinned by DECISIONS.md D4."""

    model_config = ConfigDict(extra="forbid")

    generator_model: str = "<GENERATOR_MODEL>"
    jury_models: list[str] = Field(default_factory=list)
    debate_roles: dict[str, str] = Field(default_factory=dict)
    provider: str = "openrouter"
    abstain_confidence: float = 0.55
    didactic_floor: float = 3.0
    debate_on_escalate: bool = True
    debate_rounds: int = 1
    max_doc_chars: int = 11000
    dimensions: dict[str, DimensionSpec] = Field(default_factory=lambda: DEFAULT_DIMENSIONS.copy())

    @model_validator(mode="after")
    def _validate_d4(self) -> "DidacticJuryConfig":
        self.jury_models = _unique(model for model in self.jury_models if model != self.generator_model)
        if len(self.jury_models) < 3:
            raise DidacticConfigError("D4 requires at least 3 jury models after excluding GENERATOR_MODEL.")
        missing = {"critic", "defender", "judge"} - set(self.debate_roles)
        if missing:
            raise DidacticConfigError(f"D4 debate_roles missing: {sorted(missing)}")
        role_models = [self.debate_roles[key] for key in ("critic", "defender", "judge")]
        if len(set(role_models)) != 3:
            raise DidacticConfigError("D4 requires critic/defender/judge to use different models.")
        if self.generator_model in role_models:
            raise DidacticConfigError("D4 requires debate roles to be different from GENERATOR_MODEL.")
        return self

    def warnings(self) -> list[str]:
        vendors = [model.split("/", 1)[0] for model in self.jury_models]
        return ["jury_models are not vendor-diverse by slug prefix"] if len(set(vendors)) < len(vendors) else []


DEFAULT_DIMENSIONS: dict[str, DimensionSpec] = {
    "coherence": DimensionSpec(title="Связность", question="Единый маршрут без разрывов, оборванных фраз и скачков?"),
    "scaffolding": DimensionSpec(title="Scaffolding", question="Теория главы 2 реально готовит к заданиям главы 3?"),
    "example_quality": DimensionSpec(title="Качество примеров", question="Примеры конкретны и раскрывают идею, а не заглушки?"),
    "cognitive_load": DimensionSpec(title="Когнитивная нагрузка", question="Нет повторов и перегруза, адекватная прогрессия?"),
    "school_tone": DimensionSpec(title="Тон школы", question="Peer-тон: не директивно, решение не выдаётся?"),
    "naturalness": DimensionSpec(title="Не-AI-водность", question="Живой язык без шаблонных самоповторов?"),
}


def load_didactic_config() -> DidacticJuryConfig:
    raw = get_thresholds().get("checker.didactic", {}) or {}
    return DidacticJuryConfig.model_validate(raw)


def evaluate_didactic(
    markdown: str,
    *,
    config: DidacticJuryConfig | dict[str, Any] | None = None,
    learning_outcomes: list[str] | None = None,
    signals: dict[str, Any] | None = None,
    client_factory: ClientFactory | None = None,
) -> DidacticQualityReport:
    """Run didactic PoLL evaluation and return didactic_json-compatible report."""

    resolved = _coerce_config(config)
    observed_signals = dict(signals or collect_signals(markdown))
    dimensions = [
        judge_dimension(
            dim_id,
            spec,
            markdown=markdown,
            signals=observed_signals,
            learning_outcomes=learning_outcomes or [],
            config=resolved,
            client_factory=client_factory,
        )
        for dim_id, spec in resolved.dimensions.items()
    ]
    scores = [item.score for item in dimensions]
    overall = round(statistics.median(scores), 2) if scores else 0.0
    reasons = sorted({reason for item in dimensions for reason in _human_reasons(item, resolved)})
    return DidacticQualityReport(
        dimensions=dimensions,
        overall_raw=overall,
        needs_human_review=bool(reasons),
        abstain_reasons=reasons,
        jury=resolved.jury_models,
        n_jury=len(resolved.jury_models),
        generator_model=resolved.generator_model,
        config_warnings=resolved.warnings(),
    )


def judge_dimension(
    dim_id: str,
    spec: DimensionSpec,
    *,
    markdown: str,
    signals: dict[str, Any],
    learning_outcomes: list[str],
    config: DidacticJuryConfig,
    client_factory: ClientFactory | None = None,
) -> DidacticDimensionScore:
    verdicts = {
        model: juror_score(model, dim_id, spec, markdown, signals, learning_outcomes, config, client_factory)
        for model in config.jury_models
    }
    valid_scores = [verdict.score for verdict in verdicts.values() if verdict.score is not None]
    score = round(statistics.median(valid_scores), 2) if valid_scores else 0.0
    confidence = _confidence(valid_scores, [model for model, verdict in verdicts.items() if verdict.abstain])
    result = DidacticDimensionScore(
        dimension=dim_id,
        title=spec.title,
        score=score,
        confidence=confidence,
        per_model={model: verdict.score for model, verdict in verdicts.items()},
        rationale=next((verdict.rationale for verdict in verdicts.values() if verdict.rationale), ""),
        evidence=_unique_evidence(verdict.evidence for verdict in verdicts.values()),
        abstained_models=[model for model, verdict in verdicts.items() if verdict.abstain],
    )
    low_conf = result.confidence < config.abstain_confidence
    below_floor = result.score < config.didactic_floor
    has_abstain = bool(result.abstained_models)
    result.human_review_required = low_conf or below_floor or has_abstain
    if config.debate_on_escalate and result.human_review_required:
        result.escalated = True
        result.escalate_reason = _reason(low_conf=low_conf, below_floor=below_floor, has_abstain=has_abstain)
        debate = run_debate(
            dimension=dim_id,
            title=spec.title,
            question=spec.question,
            markdown=markdown,
            signals=signals,
            jury_scores=result.per_model,
            learning_outcomes=learning_outcomes,
            config=config,
            client_factory=client_factory,
        )
        result.score = debate.final_score
        result.rationale = debate.rationale or result.rationale
        result.debate_transcript = [turn.model_dump(mode="json") for turn in debate.transcript]
        result.human_review_required = has_abstain or low_conf or result.score < config.didactic_floor
    return result


def juror_score(
    model: str,
    dim_id: str,
    spec: DimensionSpec,
    markdown: str,
    signals: dict[str, Any],
    learning_outcomes: list[str],
    config: DidacticJuryConfig,
    client_factory: ClientFactory | None = None,
) -> JurorVerdict:
    try:
        prompt = load_prompt("checker", "didactic_juror", "v1").render(
            title=spec.title,
            question=spec.question,
            learning_outcomes=", ".join(learning_outcomes) or "-",
            signals_json=_json(signals),
            markdown=markdown[: config.max_doc_chars],
        )
        return complete_typed(
            StructuredPrompt(system=_SYSTEM, user=prompt),
            JurorVerdict,
            client=_client(model, config, client_factory),
            retries=1,
            temperature=0.1,
            max_tokens=700,
        )
    except Exception:
        return _heuristic_verdict(dim_id, signals)


def collect_signals(markdown: str) -> dict[str, Any]:
    """Use C1 signals.py when present; otherwise keep the notebook mock path usable."""

    try:
        module = import_module("app.modules.checker.signals")
    except ModuleNotFoundError:
        return _fallback_signals(markdown)
    for name in ("collect_signals", "extract_signals", "analyze", "scan"):
        func = getattr(module, name, None)
        if callable(func):
            try:
                result = func(markdown)
            except TypeError:
                continue
            return result.model_dump(mode="json") if isinstance(result, BaseModel) else dict(result or {})
    return _fallback_signals(markdown)


def run(markdown: str, **kwargs: Any) -> DidacticQualityReport:
    return evaluate_didactic(markdown, **kwargs)


def _coerce_config(config: DidacticJuryConfig | dict[str, Any] | None) -> DidacticJuryConfig:
    if config is None:
        return load_didactic_config()
    return config if isinstance(config, DidacticJuryConfig) else DidacticJuryConfig.model_validate(config)


def _client(model: str, config: DidacticJuryConfig, client_factory: ClientFactory | None) -> Any:
    if client_factory is not None:
        return client_factory(model)
    return create_llm_client(provider=config.provider, model=model)


def _confidence(scores: list[float | None], abstained: list[str]) -> float:
    valid = [float(score) for score in scores if score is not None]
    if not valid:
        return 0.0
    spread = statistics.pstdev(valid) if len(valid) > 1 else 0.0
    confidence = max(0.0, 1.0 - spread / 2.0)
    return round(min(confidence, 0.5) if abstained else confidence, 2)


def _human_reasons(item: DidacticDimensionScore, config: DidacticJuryConfig) -> list[str]:
    reasons: list[str] = []
    if item.abstained_models:
        reasons.extend(f"abstain:{item.dimension}:{model}" for model in item.abstained_models)
    if item.confidence < config.abstain_confidence:
        reasons.append(f"jury_split:{item.dimension}")
    if item.score < config.didactic_floor:
        reasons.append(f"below_floor:{item.dimension}")
    return reasons


def _reason(*, low_conf: bool, below_floor: bool, has_abstain: bool) -> str:
    parts = []
    if has_abstain:
        parts.append("abstain")
    if low_conf:
        parts.append("разброс жюри")
    if below_floor:
        parts.append("ниже пола")
    return " + ".join(parts)


def _heuristic_verdict(dim_id: str, signals: dict[str, Any]) -> JurorVerdict:
    rep = float(signals.get("repetition_ratio", 0.0) or 0.0)
    near_dup = int(signals.get("near_dup", 0) or 0)
    broken = int(signals.get("broken_tables", 0) or 0)
    examples = int(signals.get("example_count", 0) or 0)
    directive = int(signals.get("directive_hits", 0) or 0)
    diagram = float(signals.get("diagram_match_avg", 1.0) or 1.0)
    if dim_id == "naturalness":
        score, rationale = 5 - min(3.2, rep * 18 + near_dup * 0.06), "Самоповторы снижают естественность."
    elif dim_id == "coherence":
        score, rationale = 5 - min(2.8, broken + near_dup * 0.04 + (1 if diagram < 0.2 else 0)), "Разрывы потока снижают связность."
    elif dim_id == "cognitive_load":
        score, rationale = 5 - min(2.7, rep * 15 + near_dup * 0.05), "Повторы повышают когнитивную нагрузку."
    elif dim_id == "example_quality":
        score, rationale = (3.7 if examples >= 3 else 2.5), "Качество примеров оценено по числу и конкретности."
    elif dim_id == "school_tone":
        score, rationale = (4.2 if directive == 0 else 3.0), "Проверен peer-тон без директивности."
    else:
        score, rationale = 3.1, "Теория частично поддерживает практику."
    evidence = [f"repetition_ratio={rep}", f"near_dup={near_dup}", f"examples={examples}"]
    return JurorVerdict(score=round(max(1.0, min(5.0, score)), 2), rationale=rationale, evidence=evidence)


def _fallback_signals(markdown: str) -> dict[str, Any]:
    sentences = _sentences(markdown)
    near_dup = _near_duplicate_pairs(sentences)
    diagrams = _diagram_topic_match(markdown)
    return {
        "repetition_ratio": round(_repetition_ratio(markdown), 3),
        "near_dup": len(near_dup),
        "near_dup_examples": near_dup[:2],
        "broken_tables": len([line for line in markdown.splitlines() if line.count("|") >= 2 and len(line) > 200]),
        "diagram_match_avg": round(sum(diagrams) / len(diagrams), 3) if diagrams else 1.0,
        "example_count": len(re.findall(r"\*\*Пример", markdown)),
        "directive_hits": len(re.findall(r"\b(сделай|нажми|введите|скопируй|выполни шаг)\b", markdown.lower())),
    }


def _sentences(text: str) -> list[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if len(item.strip()) > 25]


def _repetition_ratio(text: str, n: int = 8) -> float:
    words = re.findall(r"\w+", text.lower())
    grams = [" ".join(words[index : index + n]) for index in range(len(words) - n + 1)]
    if not grams:
        return 0.0
    counts = Counter(grams)
    return sum(value for value in counts.values() if value > 1) / len(grams)


def _near_duplicate_pairs(sentences: list[str], threshold: float = 0.7, cap: int = 40) -> list[tuple[str, str]]:
    sets = [set(re.findall(r"\w+", sentence.lower())) for sentence in sentences]
    pairs: list[tuple[str, str]] = []
    for left in range(len(sets)):
        for right in range(left + 1, len(sets)):
            a, b = sets[left], sets[right]
            if a and b and len(a & b) / len(a | b) >= threshold:
                pairs.append((sentences[left][:80], sentences[right][:80]))
                if len(pairs) >= cap:
                    return pairs
    return pairs


def _diagram_topic_match(markdown: str) -> list[float]:
    matches: list[float] = []
    for match in re.finditer(r"```mermaid(.*?)```", markdown, flags=re.S):
        heading = None
        for candidate in re.finditer(r"^#{2,3}\s+(.+)$", markdown[: match.start()], flags=re.M):
            heading = candidate.group(1)
        nodes = set(re.findall(r"[А-Яа-яЁё]{4,}", match.group(1).lower()))
        heading_words = set(re.findall(r"[А-Яа-яЁё]{4,}", (heading or "").lower()))
        matches.append(len(nodes & heading_words) / len(nodes | heading_words) if nodes or heading_words else 0.0)
    return matches


def _unique(values: Any) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(str(value))
    return out


def _unique_evidence(groups: Any) -> list[str]:
    return _unique(item for group in groups for item in group)[:4]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


_SYSTEM = "Return only valid JSON matching the requested schema."
