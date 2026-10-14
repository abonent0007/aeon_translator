"""Ранжирование и фильтрация гипотез (шаг 2.3)."""

from typing import List

from .hypothesis import Hypothesis


def rank_hypotheses(hypotheses: List[Hypothesis]) -> List[Hypothesis]:
    """Сортировка по confidence (desc); стабильно (тайбрейк — исходный порядок)."""
    return sorted(hypotheses, key=lambda hypothesis: -float(hypothesis.confidence))


def cap_hypotheses(hypotheses: List[Hypothesis], max_count: int = 4) -> List[Hypothesis]:
    """Серверный cap: не более max_count гипотез (промпт просит 2–4)."""
    return hypotheses[: max(0, int(max_count))]


def drop_contradicted(hypotheses: List[Hypothesis]) -> List[Hypothesis]:
    """Отбрасывает гипотезы, отвергнутые верификацией (contradicted)."""
    return [hypothesis for hypothesis in hypotheses if hypothesis.verified is not False]
