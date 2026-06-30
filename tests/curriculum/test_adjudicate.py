from __future__ import annotations

from app.core.models import Competency, EvidenceSource
from app.modules.curriculum.stages import stage_adjudicate


def _competency(
    *,
    name: str = "Навык",
    resolution: str = "new",
    match_score: float | None = None,
    evidence_ids: list[str] | None = None,
    atomicity: str = "atomic",
    bloom: str = "apply",
) -> Competency:
    return Competency.model_validate(
        {
            "competency_id": f"tmp-{name}",
            "canonical_name": name,
            "resolution": resolution,
            "match_score": match_score,
            "evidence_ids": evidence_ids or [],
            "atomicity": atomicity,
            "indicators": [{"text": f"делает {name}", "bloom": bloom}],
        }
    )


def _evidence(evidence_id: str, source_type: str = "vacancy") -> EvidenceSource:
    return EvidenceSource.model_validate({"evidence_id": evidence_id, "source_type": source_type})


def test_matched_candidate_gets_high_match_confidence() -> None:
    comp = _competency(resolution="matched", match_score=1.0)
    assert stage_adjudicate.score_confidence(comp, []) == 0.98


def test_fuzzy_confidence_tracks_match_score_within_bounds() -> None:
    low = _competency(resolution="fuzzy", match_score=0.40)
    high = _competency(resolution="fuzzy", match_score=0.99)
    assert stage_adjudicate.score_confidence(low, []) == 0.55
    assert stage_adjudicate.score_confidence(high, []) == 0.93


def test_evidence_with_framework_lifts_confidence() -> None:
    comp = _competency(resolution="new", evidence_ids=["e1", "e2"])
    evidence = [_evidence("e1", "framework"), _evidence("e2", "vacancy")]
    # 0.5 + 0.2*2 = 0.9, +0.1 framework = 1.0 capped at 0.97; beats new match_confidence 0.5
    assert stage_adjudicate.score_confidence(comp, evidence) == 0.97


def test_new_candidate_without_evidence_falls_to_match_floor() -> None:
    comp = _competency(resolution="new", evidence_ids=[])
    assert stage_adjudicate.score_confidence(comp, []) == 0.5


def test_council_skips_confident_matched_candidate() -> None:
    comp = _competency(resolution="matched", match_score=1.0)
    comp.confidence = stage_adjudicate.score_confidence(comp, [])
    report = stage_adjudicate.run_council([comp], use_council=True)
    assert comp.metadata.get("council_agreement") is None
    assert report["sent_to_council"] == 0


def test_council_scores_grey_zone_candidate() -> None:
    comp = _competency(resolution="new", evidence_ids=["e1", "e2"], bloom="apply")
    comp.confidence = stage_adjudicate.score_confidence(comp, [_evidence("e1"), _evidence("e2")])
    report = stage_adjudicate.run_council([comp], use_council=True)
    agreement = comp.metadata.get("council_agreement")
    assert agreement is not None
    assert 0.0 <= float(agreement) <= 1.0
    assert report["sent_to_council"] == 1
    # confidence blended: 0.6*prev + 0.4*agreement
    assert comp.metadata.get("council_ran") is True


def test_council_disabled_leaves_candidates_untouched() -> None:
    comp = _competency(resolution="new", evidence_ids=["e1"])
    comp.confidence = stage_adjudicate.score_confidence(comp, [_evidence("e1")])
    before = comp.confidence
    report = stage_adjudicate.run_council([comp], use_council=False)
    assert comp.confidence == before
    assert comp.metadata.get("council_agreement") is None
    assert report["council_executed"] == 0


def test_non_atomic_candidate_is_not_sent_to_council() -> None:
    comp = _competency(resolution="new", atomicity="composite")
    comp.confidence = stage_adjudicate.score_confidence(comp, [])
    report = stage_adjudicate.run_council([comp], use_council=True)
    assert report["sent_to_council"] == 0
