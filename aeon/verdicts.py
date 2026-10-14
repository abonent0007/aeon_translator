"""
Обратная совместимость: таксономия вердиктов переехала в
aeon/verification/verdicts.py (Verification 2.0).

Реэкспорт: `from aeon.verdicts import ...` продолжает работать.
Новый код должен импортировать из `aeon.verification.verdicts`.
"""

from .verification.verdicts import (  # noqa: F401
    ABSTAINED_VERDICTS,
    ALL_VERDICTS,
    NEGATIVE_VERDICTS,
    NEUTRAL_VERDICTS,
    POSITIVE_VERDICTS,
    VERDICT_ABSTAINED,
    VERDICT_COHERENT,
    VERDICT_CONTRADICTED,
    VERDICT_GROUNDED,
    VERDICT_INCOHERENT,
    VERDICT_NEEDS_REVIEW,
    VERDICT_SUPPORTED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
    VERDICT_VERIFIED,
    is_abstained,
    is_negative,
    is_neutral,
    is_positive,
)
