"""
AEON verdicts — таксономия вердиктов верификации (задел Verification 2.0).

Ключевой принцип (кураторский, Фаза 1):
  - `contradicted` — НЕГАТИВНЫЙ вердикт (данные противоречат источнику);
  - `unverifiable_due_to_missing_data` — НЕЙТРАЛЬНЫЙ (данных нет — не штрафуем,
    а явно указываем на пробел; для фрагментарных текстов это норма).
"""

VERDICT_VERIFIED = "verified"
VERDICT_NEEDS_REVIEW = "needs_review"
VERDICT_CONTRADICTED = "contradicted"
VERDICT_UNVERIFIABLE_MISSING_DATA = "unverifiable_due_to_missing_data"

ALL_VERDICTS = (
    VERDICT_VERIFIED,
    VERDICT_NEEDS_REVIEW,
    VERDICT_CONTRADICTED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
)

#: Вердикты, которые считаются негативными (штрафуются агрегатором).
NEGATIVE_VERDICTS = frozenset({VERDICT_CONTRADICTED})

#: Вердикты, не понижающие уверенность (отсутствие данных ≠ ошибка).
NEUTRAL_VERDICTS = frozenset({VERDICT_UNVERIFIABLE_MISSING_DATA})


def is_negative(verdict: str) -> bool:
    """True только для противоречия источнику (не для нехватки данных)."""
    return verdict in NEGATIVE_VERDICTS


def is_neutral(verdict: str) -> bool:
    """True для нейтральных вердиктов (нехватка данных не штрафуется)."""
    return verdict in NEUTRAL_VERDICTS
