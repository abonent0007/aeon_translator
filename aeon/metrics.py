"""
AEON Metrics — лёгкий сборщик метрик производительности.
Только стандартная библиотека, без внешних зависимостей.

Собирает: время на атом, количество сетевых вызовов, hit-rate кэша.
Сводка автоматически выводится в конце pytest-сессии
(см. pytest_terminal_summary в tests/conftest.py).
"""

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class Metrics:
    """Потокобезопасный счётчик метрик."""

    atoms_processed: int = 0
    network_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    timings: Dict[str, List[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )

    # ── запись событий ──

    def record_atom(self, n: int = 1) -> None:
        with self._lock:
            self.atoms_processed += n

    def record_network_call(self, n: int = 1) -> None:
        with self._lock:
            self.network_calls += n

    def record_cache(self, hit: bool) -> None:
        with self._lock:
            if hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    @contextmanager
    def timeit(self, name: str = "default") -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt = time.perf_counter() - t0
            with self._lock:
                self.timings.setdefault(name, []).append(dt)

    # ── сводка ──

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            cache_lookups = self.cache_hits + self.cache_misses
            atom_times = self.timings.get("atom", [])
            avg_atom: Optional[float] = (
                round(sum(atom_times) / len(atom_times), 3) if atom_times else None
            )
            return {
                "atoms_processed": self.atoms_processed,
                "network_calls": self.network_calls,
                "network_calls_per_atom": (
                    round(self.network_calls / self.atoms_processed, 2)
                    if self.atoms_processed else None
                ),
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate": (
                    round(self.cache_hits / cache_lookups, 2) if cache_lookups else None
                ),
                "avg_time_per_atom_sec": avg_atom,
            }

    def format_summary(self) -> str:
        s = self.snapshot()

        def _fmt(value: Any) -> Any:
            return "n/a" if value is None else value

        avg_atom = s["avg_time_per_atom_sec"]
        avg_atom_str = "n/a" if avg_atom is None else f"{avg_atom}s"

        return "\n".join([
            f"  atoms_processed:   {s['atoms_processed']}",
            f"  network_calls:     {s['network_calls']} "
            f"(avg {_fmt(s['network_calls_per_atom'])}/atom)",
            f"  cache_hit_rate:    {_fmt(s['cache_hit_rate'])}",
            f"  avg_time_per_atom: {avg_atom_str}",
        ])

    def reset(self) -> None:
        with self._lock:
            self.atoms_processed = 0
            self.network_calls = 0
            self.cache_hits = 0
            self.cache_misses = 0
            self.timings.clear()


# Глобальный синглтон (используется модулями v4.0)
METRICS = Metrics()


def reset_metrics() -> None:
    """Сбросить глобальные метрики (используется в тестах)."""
    METRICS.reset()
