"""Confidence and council adjudication over resolved competencies.

Ported from Spravochnik ``stage_brief_to_catalog`` (``_confidence`` / ``run_council``).
Pure scoring: the catalog matcher (``CurriculumCatalogRepo.resolve_competency``) must
have already set ``resolution`` / ``match_score`` before these run.
"""

from __future__ import annotations

import os

from app.core.models import BLOOM_RANK, Competency, EvidenceSource

TAU_CONFIDENCE = float(os.getenv("TAU_CONFIDENCE", "0.75"))
# Juror identities; legacy used concrete model ids, only the family prefix matters here.
MODEL_PANEL = ("openai", "anthropic", "local")
# Bloom level at/above which a brand-new high-order skill makes the strict juror abstain.
_STRICT_BLOOM_RANK = BLOOM_RANK["analyze"]


def score_confidence(comp: Competency, evidence: list[EvidenceSource]) -> float:
    """Deterministic confidence from evidence strength vs catalog-match strength."""
    evs = [item for item in evidence if item.evidence_id in comp.evidence_ids]
    has_framework = any(item.source_type in ("framework", "syllabus") for item in evs)
    evidence_confidence = min(min(0.5 + 0.2 * len(evs), 0.95) + (0.1 if has_framework else 0.0), 0.97)
    match_confidence = 0.0
    if comp.resolution in {"matched", "alias"}:
        match_confidence = 0.98
    elif comp.resolution == "fuzzy":
        match_confidence = min(max(comp.match_score or 0.0, 0.55), 0.93)
    elif comp.resolution == "new":
        match_confidence = 0.5
    return round(max(evidence_confidence if evs else 0.0, match_confidence), 2)


def _is_resolvable(comp: Competency) -> bool:
    return comp.atomicity == "atomic"


def _needs_panel(comp: Competency) -> bool:
    return not (comp.resolution in ("matched", "alias") and comp.confidence >= TAU_CONFIDENCE)


def _juror(model: str, comp: Competency) -> int:
    evidence_count = len(set(comp.evidence_ids))
    if model.startswith("openai"):
        return 1
    if model.startswith("anthropic"):
        return 1 if evidence_count >= 2 else 0
    return 0 if (comp.resolution == "new" and BLOOM_RANK[comp.bloom_level] >= _STRICT_BLOOM_RANK) else 1


def select_council_candidates(comps: list[Competency]) -> list[Competency]:
    return [comp for comp in comps if _is_resolvable(comp) and _needs_panel(comp)]


def run_council(comps: list[Competency], *, use_council: bool = True) -> dict[str, int]:
    """Vote on grey-zone candidates and blend council agreement into confidence."""
    council_candidates = select_council_candidates(comps)
    if use_council:
        for comp in council_candidates:
            votes = [_juror(model, comp) for model in MODEL_PANEL]
            agreement = round(sum(votes) / len(votes), 2)
            comp.metadata["council_ran"] = True
            comp.metadata["council_agreement"] = agreement
            comp.confidence = round(0.6 * comp.confidence + 0.4 * agreement, 2)
    return {
        "sent_to_council": len(council_candidates),
        "council_executed": len([comp for comp in comps if comp.metadata.get("council_ran")]),
    }


def score_confidences(comps: list[Competency], evidence: list[EvidenceSource]) -> None:
    """Set ``confidence`` on every atomic candidate in place."""
    for comp in comps:
        if _is_resolvable(comp):
            comp.confidence = score_confidence(comp, evidence)
