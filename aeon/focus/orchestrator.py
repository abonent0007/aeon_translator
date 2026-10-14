"""
AEON Multi-focus — оркестратор (шаг 2.5).

Роли НЕЗАВИСИМЫ: общий только Atom (+pack +linguistic layers) на входе;
результаты ролей друг другу не передаются. >1 роли — параллельно
(ThreadPoolExecutor; вызовы I/O-bound — GIL не блокирует реальную сеть).
Alias "all" = historian+philosopher+linguist; esoteric — ТОЛЬКО явно
(стоп-точка №1: анти-псевдонаучный guardrail + opt-in).
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from ..config import CONFIG, ConfigError
from ..llm_client import DeepSeekClient
from .aggregator import MultiFocusResult, aggregate
from .base import FocusAnalysis, FocusContext, FocusRole
from .esoteric import EsotericRole
from .historian import HistorianRole
from .linguist import LinguistRole
from .philosopher import PhilosopherRole

DEFAULT_ROLES = ("historian", "philosopher", "linguist")
ALL_ROLES = ("historian", "philosopher", "linguist", "esoteric")


class MultiFocusOrchestrator:
    """Параллельный запуск независимых ролей + сводка (без арбитража)."""

    def __init__(self, llm_client=None, config=None):
        full = config or CONFIG
        self.llm = llm_client or DeepSeekClient()
        self.cfg = full
        shared = {"llm": self.llm}
        self._roles: Dict[str, FocusRole] = {
            "historian": HistorianRole(**shared),
            "philosopher": PhilosopherRole(**shared),
            "linguist": LinguistRole(**shared),
            "esoteric": EsotericRole(**shared),
        }

    def validate_roles(self, roles: List[str]) -> List[str]:
        unknown = [name for name in roles if name not in self._roles]
        if unknown:
            raise ConfigError(
                f"Неизвестные роли фокуса: {unknown}. Доступные: {list(self._roles)}"
            )
        return list(dict.fromkeys(roles))  # порядок запроса, без дублей

    def run(self, atom: Any, *, roles: Optional[List[str]] = None,
            pack: Any = None, linguistic_layers: Any = None,
            trace_id: Optional[str] = None) -> MultiFocusResult:
        """Запуск ролей; ConfigError при неизвестной роли."""
        requested = list(roles) if roles else list(DEFAULT_ROLES)
        if "all" in requested:
            requested = list(DEFAULT_ROLES)  # esoteric — только явно
        ordered = self.validate_roles(requested)

        if not self.llm.available:
            return MultiFocusResult("llm_unavailable", [], {}, False, 0, trace_id)
        if not ordered:
            return MultiFocusResult("ok", [], {}, False, 0, trace_id)

        context = FocusContext(
            atom=atom, language_pack=pack,
            linguistic_layers=linguistic_layers, trace_id=trace_id,
        )

        if len(ordered) == 1:
            analyses = [self._roles[ordered[0]].analyze(context)]
        else:
            analyses = self._run_parallel(ordered, context)

        return aggregate(analyses, trace_id=trace_id)

    def _run_parallel(self, ordered: List[str],
                      context: FocusContext) -> List[FocusAnalysis]:
        analyses: Dict[str, FocusAnalysis] = {}
        with ThreadPoolExecutor(max_workers=len(ordered)) as pool:
            futures = {
                pool.submit(self._roles[name].analyze, context): name
                for name in ordered
            }
            for future, name in futures.items():
                analyses[name] = future.result()
        return [analyses[name] for name in ordered]
