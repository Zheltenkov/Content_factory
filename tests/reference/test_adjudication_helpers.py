from __future__ import annotations

from app.modules.reference import adjudication as adj


def test_format_catalog_similarity_splits_into_similarity_and_novelty() -> None:
    assert adj.format_catalog_similarity(None) == (None, None)
    assert adj.format_catalog_similarity(71.11) == ("71.11", "28.89")
    assert adj.format_catalog_similarity(150) == ("100.00", "0.00")
    assert adj.format_catalog_similarity(-5) == ("0.00", "100.00")


def test_similarity_hint_matched_is_strong() -> None:
    hint = adj.build_similarity_hint(100.0, "matched", True)
    assert hint["class"] == "strong"
    assert hint["label"] == "Покрывает"


def test_similarity_hint_weak_for_low_score_with_nearest() -> None:
    hint = adj.build_similarity_hint(40.0, "new", True)
    assert hint["class"] == "weak"
    assert hint["label"] == "Слабое совпадение"


def test_similarity_hint_new_without_nearest_is_neutral() -> None:
    hint = adj.build_similarity_hint(0.0, "new", False)
    assert hint["class"] == "neutral"
    assert hint["label"] == "Новое"


def test_similarity_hint_flags_suspicious_match() -> None:
    hint = adj.build_similarity_hint(95.0, "matched", True, ["catalog_match_suspicious"])
    assert hint["class"] == "weak"
    assert hint["label"] == "Подозрительный матч"


def test_recommended_action_create_for_new() -> None:
    action = adj.build_candidate_recommended_action(10.0, "new", False)
    assert action["code"] == "create"


def test_recommended_action_link_for_fuzzy_with_nearest() -> None:
    action = adj.build_candidate_recommended_action(88.0, "fuzzy", True, nearest_name="SQL")
    assert action["code"] == "link"
    assert action["target"] == "SQL"


def test_recommended_action_done_when_already_accepted() -> None:
    action = adj.build_candidate_recommended_action(88.0, "fuzzy", True, decision="accepted")
    assert action["code"] == "done"


def test_recommended_action_rejected() -> None:
    action = adj.build_candidate_recommended_action(0.0, "new", False, decision="rejected")
    assert action["code"] == "rejected"
