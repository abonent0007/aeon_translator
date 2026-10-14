"""
AEON verdicts — таксономия вердиктов верификации (Verification 2.0).

Принципы (кураторские, Фаза 1):
  - positive: grounded / supported / coherent (+ агрегатный verified);
  - neutral:  unverifiable_due_to_missing_data — данных нет (лакуны, offline,
    source_unavailable). НЕ штрафуется: отсутствие данных ≠ ошибка;
  - negative: contradicted / incoherent — штрафуются, доминируют в агрегате;
  - abstained: агент/система воздержалась («Я не знаю»).
"""

VERDICT_VERIFIED = "verified"
VERDICT_NEEDS_REVIEW = "needs_review"
VERDICT_CONTRADICTED = "contradicted"
VERDICT_UNVERIFIABLE_MISSING_DATA = "unverifiable_due_to_missing_data"
VERDICT_GROUNDED = "grounded"
VERDICT_SUPPORTED = "supported"
VERDICT_COHERENT = "coherent"
VERDICT_INCOHERENT = "incoherent"
VERDICT_ABSTAINED = "abstained"

ALL_VERDICTS = (
    VERDICT_VERIFIED,
    VERDICT_NEEDS_REVIEW,
    VERDICT_CONTRADICTED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
    VERDICT_GROUNDED,
    VERDICT_SUPPORTED,
    VERDICT_COHERENT,
    VERDICT_INCOHERENT,
    VERDICT_ABSTAINED,
)

#: Положительные вердикты (уверенность учитывается агрегатором).
POSITIVE_VERDICTS = frozenset({
    VERDICT_VERIFIED,
    VERDICT_GROUNDED,
    VERDICT_SUPPORTED,
    VERDICT_COHERENT,
})

#: Негативные вердикты (доминируют в агрегате).
NEGATIVE_VERDICTS = frozenset({VERDICT_CONTRADICTED, VERDICT_INCOHERENT})

#: Нейтральные вердикты (не штрафуются). needs_review — НЕ вердикт агента,
#: а агрегатный флаг CombinedVerdict (в таксономию не входит).
NEUTRAL_VERDICTS = frozenset({VERDICT_UNVERIFIABLE_MISSING_DATA})

#: Воздержание.
ABSTAINED_VERDICTS = frozenset({VERDICT_ABSTAINED})


def is_positive(verdict: str) -> bool:
    return verdict in POSITIVE_VERDICTS


def is_negative(verdict: str) -> bool:
    """True только для противоречия (не для нехватки данных)."""
    return verdict in NEGATIVE_VERDICTS


def is_neutral(verdict: str) -> bool:
    """True для нейтральных вердиктов (нехватка данных не штрафуется)."""
    return verdict in NEUTRAL_VERDICTS


def is_abstained(verdict: str) -> bool:
    return verdict in ABSTAINED_VERDICTS
