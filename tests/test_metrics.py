"""Тесты сборщика метрик (aeon/metrics.py)."""

from aeon.metrics import METRICS, Metrics, reset_metrics


def test_counters_and_snapshot():
    m = Metrics()
    m.record_atom(2)
    m.record_network_call(3)
    m.record_cache(hit=True)
    m.record_cache(hit=False)

    s = m.snapshot()
    assert s["atoms_processed"] == 2
    assert s["network_calls"] == 3
    assert s["network_calls_per_atom"] == 1.5
    assert s["cache_hit_rate"] == 0.5


def test_empty_snapshot_is_na():
    s = Metrics().snapshot()
    assert s["network_calls_per_atom"] is None
    assert s["cache_hit_rate"] is None
    assert s["avg_time_per_atom_sec"] is None


def test_timeit_records_timings():
    m = Metrics()
    with m.timeit("atom"):
        pass
    with m.timeit("atom"):
        pass

    s = m.snapshot()
    assert s["avg_time_per_atom_sec"] is not None
    assert s["avg_time_per_atom_sec"] >= 0


def test_reset_clears_everything():
    m = Metrics()
    m.record_atom()
    m.record_network_call()
    m.record_cache(hit=True)
    with m.timeit("atom"):
        pass

    m.reset()
    s = m.snapshot()
    assert s["atoms_processed"] == 0
    assert s["network_calls"] == 0
    assert s["cache_hits"] == 0
    assert s["cache_misses"] == 0
    assert s["avg_time_per_atom_sec"] is None


def test_global_singleton_and_summary_format():
    reset_metrics()
    METRICS.record_atom()
    METRICS.record_network_call(5)
    METRICS.record_cache(hit=True)

    text = METRICS.format_summary()
    assert "atoms_processed" in text
    assert "cache_hit_rate" in text
    assert "network_calls" in text
    assert "avg" in text
