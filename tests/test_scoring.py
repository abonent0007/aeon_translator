"""Тесты скоринга кандидатов (шаг 1.2) — 0 сети."""

from aeon.entity_linking import SearchCandidate, rank_candidates, score_candidate


def _cand(qid, label, match_type="label", match_language="en", description="", rank=0):
    return SearchCandidate(
        qid=qid,
        label=label,
        description=description,
        match_type=match_type,
        match_language=match_language,
        rank=rank,
    )


def test_scoring_exact_beats_prefix():
    exact = _cand("Q1", "Alex")
    prefix = _cand("Q2", "Alexander")

    assert score_candidate(exact, "Alex") > score_candidate(prefix, "Alex")


def test_link_confidence_range():
    candidates = [
        _cand("Q1", "Plato", "label", "en", "philosopher"),
        _cand("Q2", "Платон", "alias", "ru"),
        _cand("Q3", "plato", "description", "en"),
        _cand("Q4", "xyz", "unknown", "de"),
    ]
    for candidate in candidates:
        score = score_candidate(candidate, "Plato")
        assert 0.0 <= score <= 1.0


def test_language_match_scores_higher():
    english = _cand("Q1", "Plato", "label", "en")
    german = _cand("Q2", "Plato", "label", "de")

    assert score_candidate(english, "Plato", language="en") > score_candidate(
        german, "Plato", language="en"
    )


def test_description_presence_bonus():
    with_description = _cand("Q1", "Plato", description="ancient philosopher")
    without_description = _cand("Q2", "Plato")

    assert score_candidate(with_description, "Plato") > score_candidate(
        without_description, "Plato"
    )


def test_match_type_weight_order():
    label = _cand("Q1", "Plato", "label")
    entity = _cand("Q2", "Plato", "entity")
    alias = _cand("Q3", "Plato", "alias")
    description = _cand("Q4", "Plato", "description")

    scores = [
        score_candidate(label, "Plato"),
        score_candidate(entity, "Plato"),
        score_candidate(alias, "Plato"),
        score_candidate(description, "Plato"),
    ]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > scores[-1]


def test_rank_candidates_ordering_and_tiebreak():
    candidates = [_cand("Q2", "Alexander"), _cand("Q1", "Alex"), _cand("Q3", "Alex")]

    ranked = rank_candidates(candidates, "Alex")

    assert [item.candidate.qid for item in ranked[:2]] == ["Q1", "Q3"]  # равные — по rank
    assert ranked[-1].candidate.qid == "Q2"
    scores = [item.score for item in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_candidates_empty():
    assert rank_candidates([], "query") == []


def test_weights_override_changes_ordering():
    """Веса переопределяемы (config/env): language-only веса меняют выбор."""
    exact_wrong_lang = _cand("Q1", "Plato", "label", "de")
    prefix_right_lang = _cand("Q2", "Platon", "label", "en")

    default_best = rank_candidates([exact_wrong_lang, prefix_right_lang], "Plato")[0]
    assert default_best.candidate.qid == "Q1"  # exactness доминирует

    language_only = {"type": 0.0, "exactness": 0.0, "language": 1.0, "description": 0.0}
    lang_best = rank_candidates(
        [exact_wrong_lang, prefix_right_lang], "Plato", weights=language_only
    )[0]
    assert lang_best.candidate.qid == "Q2"  # язык решает


def test_scoring_weights_from_config_defaults():
    from aeon.entity_linking import scoring_weights_from_config

    weights = scoring_weights_from_config()
    assert weights["type"] == 0.40
    assert weights["exactness"] == 0.35
    assert weights["language"] == 0.15
    assert weights["description"] == 0.10
