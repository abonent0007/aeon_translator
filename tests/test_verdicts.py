"""Тесты таксономии вердиктов (задел Verification 2.0, шаг 1.3)."""

from aeon.verdicts import (
    VERDICT_CONTRADICTED,
    VERDICT_NEEDS_REVIEW,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
    VERDICT_VERIFIED,
    is_negative,
    is_neutral,
)


def test_contradicted_is_negative():
    assert is_negative(VERDICT_CONTRADICTED) is True


def test_missing_data_is_neutral_not_negative():
    assert is_neutral(VERDICT_UNVERIFIABLE_MISSING_DATA) is True
    assert is_negative(VERDICT_UNVERIFIABLE_MISSING_DATA) is False


def test_verified_and_review_are_neither():
    assert is_negative(VERDICT_VERIFIED) is False
    assert is_neutral(VERDICT_VERIFIED) is False
    assert is_negative(VERDICT_NEEDS_REVIEW) is False
    assert is_neutral(VERDICT_NEEDS_REVIEW) is False
