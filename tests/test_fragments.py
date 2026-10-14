"""Тесты фрагментов (шаг 1.2): детекция лакун + completeness атома."""

from aeon.semantic_atom import (
    FRAGMENT_THRESHOLD,
    compute_completeness,
    detect_lacunae,
)


def test_fragment_detection_brackets():
    assert detect_lacunae("текст [...] продолжение") is True
    assert detect_lacunae("[lacuna] здесь был текст") is True
    assert detect_lacunae("фраза … оборвана") is True
    assert detect_lacunae("⸢нечитаемо⸣") is True


def test_detect_lacunae_clean_text():
    assert detect_lacunae("Полный текст без пропусков.") is False
    assert detect_lacunae("") is False


def test_completeness_full():
    score = compute_completeness(
        intent="statement",
        domain="philosophy",
        entities=["e"],
        semantic_roles={"agent": "x"},
        evidence=["quote"],
    )
    assert score == 1.0


def test_completeness_score_partial_2_of_5():
    score = compute_completeness(
        intent="statement",
        domain="",
        entities=[],
        semantic_roles={},
        evidence=["quote"],
    )
    assert score == 0.4  # 2 из 5 полей заполнены


def test_completeness_empty():
    score = compute_completeness(
        intent="", domain="", entities=[], semantic_roles={}, evidence=[]
    )
    assert score == 0.0


def test_fragment_threshold_value():
    assert FRAGMENT_THRESHOLD == 0.5
