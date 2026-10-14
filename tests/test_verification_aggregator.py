"""Тесты CVI-агрегатора (Verification 2.0)."""

from aeon.config import CONFIG
from aeon.verification.aggregator import Aggregator
from aeon.verification.base import Verdict
from aeon.verification.verdicts import (
    VERDICT_ABSTAINED,
    VERDICT_COHERENT,
    VERDICT_CONTRADICTED,
    VERDICT_GROUNDED,
    VERDICT_SUPPORTED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
    VERDICT_VERIFIED,
)

AGG = Aggregator(CONFIG.verification, review_threshold=0.85)


def v(agent, verdict, confidence):
    return Verdict(verdict=verdict, confidence=confidence, agent=agent)


def test_aggregator_all_positive():
    combined = AGG.combine({
        "detective": v("detective", VERDICT_GROUNDED, 0.9),
        "expert": v("expert", VERDICT_SUPPORTED, 0.9),
        "logician": v("logician", VERDICT_COHERENT, 0.9),
    })

    assert combined.verdict == VERDICT_VERIFIED
    assert combined.overall_confidence == 0.9
    assert combined.abstained is False
    assert combined.needs_review is False
    assert len(combined.reasoning_trace) == 3


def test_aggregator_one_negative_dominates():
    combined = AGG.combine({
        "detective": v("detective", VERDICT_CONTRADICTED, 0.8),
        "expert": v("expert", VERDICT_SUPPORTED, 0.95),
        "logician": v("logician", VERDICT_COHERENT, 0.9),
    })

    assert combined.verdict == VERDICT_CONTRADICTED
    assert combined.overall_confidence == 0.8
    assert combined.abstained is False


def test_aggregator_all_abstain():
    combined = AGG.combine({
        "detective": v("detective", VERDICT_ABSTAINED, 0.0),
        "expert": v("expert", VERDICT_ABSTAINED, 0.0),
        "logician": v("logician", VERDICT_ABSTAINED, 0.0),
    })

    assert combined.verdict == VERDICT_ABSTAINED
    assert combined.abstained is True


def test_aggregator_below_threshold():
    combined = AGG.combine({
        "detective": v("detective", VERDICT_GROUNDED, 0.55),
        "expert": v("expert", VERDICT_UNVERIFIABLE_MISSING_DATA, 0.3),
        "logician": v("logician", VERDICT_COHERENT, 0.4),
    })

    assert combined.overall_confidence == 0.475
    assert combined.verdict == VERDICT_ABSTAINED
    assert combined.abstained is True


def test_aggregator_needs_review_band():
    combined = AGG.combine({
        "detective": v("detective", VERDICT_GROUNDED, 0.7),
        "expert": v("expert", VERDICT_SUPPORTED, 0.65),
        "logician": v("logician", VERDICT_COHERENT, 0.75),
    })

    assert combined.verdict == VERDICT_VERIFIED
    assert combined.needs_review is True  # средняя 0.70 < 0.85


def test_verdict_taxonomy_fragment_neutral():
    """Фрагмент/нехватка данных НЕ штрафуются: нейтральные не тянут вниз."""
    combined = AGG.combine({
        "detective": v("detective", VERDICT_UNVERIFIABLE_MISSING_DATA, 0.2),
        "expert": v("expert", VERDICT_UNVERIFIABLE_MISSING_DATA, 0.3),
        "logician": v("logician", VERDICT_COHERENT, 0.9),
    })

    assert combined.verdict == VERDICT_VERIFIED
    assert combined.overall_confidence == 0.9
    assert combined.abstained is False


def test_aggregator_single_claim_all_neutral_abstains():
    """Один claim: логик abstained (не trivially coherent) → итог abstained."""
    combined = AGG.combine({
        "detective": v("detective", VERDICT_ABSTAINED, 0.5),
        "expert": v("expert", VERDICT_UNVERIFIABLE_MISSING_DATA, 0.4),
        "logician": v("logician", VERDICT_ABSTAINED, 0.0),
    })

    assert combined.verdict == VERDICT_ABSTAINED
    assert combined.abstained is True
