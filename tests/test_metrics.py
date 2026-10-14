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
    assert s["avg_time_per_atom_local"] is None
    assert s["avg_time_per_atom_network"] is None


def test_timeit_records_timings():
    m = Metrics()
    with m.timeit("atom"):
        pass
    with m.timeit("atom"):
        pass
    with m.timeit("atom_local"):
        pass
    with m.timeit("atom_network"):
        pass

    s = m.snapshot()
    assert s["avg_time_per_atom_sec"] is not None
    assert s["avg_time_per_atom_sec"] >= 0
    assert s["avg_time_per_atom_local"] is not None
    assert s["avg_time_per_atom_network"] is not None


def test_reset_clears_everything():
    m = Metrics()
    m.record_atom()
    m.record_network_call()
    m.record_cache(hit=True)
    with m.timeit("atom"):
        pass
    with m.timeit("atom_local"):
        pass

    m.reset()
    s = m.snapshot()
    assert s["atoms_processed"] == 0
    assert s["network_calls"] == 0
    assert s["cache_hits"] == 0
    assert s["cache_misses"] == 0
    assert s["avg_time_per_atom_sec"] is None
    assert s["avg_time_per_atom_local"] is None


def test_global_singleton_and_summary_format():
    reset_metrics()
    METRICS.record_atom()
    METRICS.record_network_call(5)
    METRICS.record_cache(hit=True)

    text = METRICS.format_summary()
    assert "atoms_processed" in text
    assert "cache_hit_rate" in text
    assert "network_calls" in text
    assert "(local " in text


def test_cache_namespaces_are_separate():
    m = Metrics()
    m.record_cache(hit=True)
    m.record_cache(hit=True)
    m.record_cache(hit=False, namespace="redirect")

    s = m.snapshot()
    assert s["cache_hit_rate"] == 1.0
    assert s["redirect_cache_hit_rate"] == 0.0
    assert s["cache_hits_redirect"] == 0
    assert s["cache_misses_redirect"] == 1


def test_redirect_rate_in_summary():
    reset_metrics()
    METRICS.record_cache(hit=True, namespace="redirect")

    text = METRICS.format_summary()
    assert "redirect: 1.0" in text


def test_offline_namespace_and_gauge():
    m = Metrics()
    m.record_cache(hit=True, namespace="offline")
    m.record_cache(hit=False, namespace="offline")
    m.record_offline_dump_age(12.0)

    s = m.snapshot()
    assert s["offline_cache_hit_rate"] == 0.5
    assert s["offline_dump_age_days"] == 12.0
    assert "dump age" in m.format_summary()


def test_offline_age_reset():
    m = Metrics()
    m.record_offline_dump_age(5.0)
    m.reset()
    assert m.snapshot()["offline_dump_age_days"] is None
