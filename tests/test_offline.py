"""Тесты Offline Knowledge Adapters (шаг 2.6) — mock, 0 сети."""

import json
from pathlib import Path

import pytest

from aeon.metrics import METRICS, reset_metrics
from aeon.offline import (
    OfflineDumpError,
    PleiadesOfflineAdapter,
    TrismegistosOfflineAdapter,
)
from aeon.offline import registry as offline_registry

DUMPS = Path(__file__).resolve().parent / "fixtures" / "dumps"
SAMPLE = DUMPS / "pleiades_sample.jsonl"

META = {
    "source": "pleiades", "dump_version": "2026.01", "dump_date": "2026-09-01",
    "license": "CC-BY-3.0",
    "license_file_sha256": "a" * 64,
}


def make_adapter(tmp_path):
    return PleiadesOfflineAdapter(db_path=str(tmp_path / "offline.db"))


def write_dump(path: Path, meta: dict, rows: list, broken_line: str = None):
    lines = [json.dumps({"meta": meta}, ensure_ascii=False)]
    for row in rows:
        lines.append(json.dumps(row, ensure_ascii=False))
    if broken_line is not None:
        lines.append(broken_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_pleiades_load_small_dump(tmp_path):
    adapter = make_adapter(tmp_path)

    result = adapter.load(SAMPLE)

    assert result["status"] == "loaded"
    assert result["rows"] == 5
    assert adapter.loaded is True
    adapter.close()


def test_pleiades_lookup_hit(tmp_path):
    adapter = make_adapter(tmp_path)
    adapter.load(SAMPLE)

    record = adapter.lookup("579885")

    assert record is not None
    assert record.title == "Athenae"
    assert record.place_types == ["settlement"]
    assert record.repr_point == [23.725, 37.975]
    assert record.source == "pleiades"
    adapter.close()


def test_pleiades_lookup_miss_returns_none(tmp_path):
    adapter = make_adapter(tmp_path)
    adapter.load(SAMPLE)

    assert adapter.lookup("999999999") is None
    adapter.close()


def test_pleiades_provenance_includes_license_sha256(tmp_path):
    adapter = make_adapter(tmp_path)
    adapter.load(SAMPLE)

    provenance = adapter.provenance()

    assert provenance is not None
    assert provenance.license == "CC-BY-3.0"
    assert provenance.license_file_sha256 == "a" * 64
    assert provenance.dump_version == "2026.01"
    assert provenance.bundle_size_bytes > 0
    adapter.close()


def test_load_rollback_on_malformed_batch(tmp_path):
    """Дополнение A: битая запись → rollback, 0 записей, meta не обновлена."""
    bad_dump = write_dump(
        tmp_path / "bad.jsonl", META,
        rows=[{"id": "1", "title": "A"}, {"id": "2", "title": "B"}],
        broken_line='{"id": "3", "title": ',
    )
    adapter = make_adapter(tmp_path)

    with pytest.raises(OfflineDumpError, match="битая запись"):
        adapter.load(bad_dump)

    assert adapter.provenance() is None        # meta не записана
    assert adapter.lookup("1") is None        # ни одной записи
    adapter.close()


def test_indexes_present_after_load(tmp_path):
    """Дополнение B: индексы создаются после загрузки."""
    adapter = make_adapter(tmp_path)
    adapter.load(SAMPLE)

    with adapter._store._lock:
        names = {
            row[0] for row in adapter._store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }

    assert "idx_pleiades_title" in names
    assert "idx_pleiades_place_types" in names
    adapter.close()


def test_reload_same_version_skips(tmp_path, monkeypatch):
    """Дополнение C: та же версия → skip (без перезагрузки)."""
    events = []
    monkeypatch.setattr(
        "aeon.offline.base.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    adapter = make_adapter(tmp_path)
    adapter.load(SAMPLE)

    result = adapter.load(SAMPLE)

    assert result["status"] == "skipped"
    assert adapter.lookup("579885") is not None  # данные на месте
    assert not [e for e in events if e["msg"] == "offline_dump_upgraded"]
    adapter.close()


def test_reload_new_version_replaces(tmp_path, monkeypatch):
    """Дополнение C: новая версия → replace + событие upgrade."""
    events = []
    monkeypatch.setattr(
        "aeon.offline.base.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    adapter = make_adapter(tmp_path)
    adapter.load(SAMPLE)
    new_meta = {**META, "dump_version": "2026.02", "dump_date": "2026-10-01"}
    new_dump = write_dump(
        tmp_path / "new.jsonl", new_meta,
        rows=[{"id": "111", "title": "Nova", "place_types": [],
               "repr_point": None, "uri": "", "dump_version": "2026.02"}],
    )

    result = adapter.load(new_dump)

    assert result["status"] == "loaded"
    assert adapter.lookup("111").title == "Nova"
    assert adapter.lookup("579885") is None      # старые записи заменены
    upgraded = [e for e in events if e["msg"] == "offline_dump_upgraded"]
    assert len(upgraded) == 1
    assert upgraded[0]["old_version"] == "2026.01"
    adapter.close()


def test_offline_dump_stale_warning(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(
        "aeon.offline.base.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    old_meta = {**META, "dump_date": "2024-01-01"}
    stale_dump = write_dump(
        tmp_path / "stale.jsonl", old_meta,
        rows=[{"id": "1", "title": "X", "place_types": [], "repr_point": None,
               "uri": "", "dump_version": "2026.01"}],
    )
    adapter = make_adapter(tmp_path)

    adapter.load(stale_dump)

    stale = [e for e in events if e["msg"] == "offline_dump_stale"]
    assert len(stale) == 1
    assert stale[0]["age_days"] > 90
    adapter.close()


def test_offline_metrics_recorded(tmp_path):
    reset_metrics()
    adapter = make_adapter(tmp_path)
    adapter.load(SAMPLE)

    adapter.lookup("579885")   # hit
    adapter.lookup("nope")     # miss

    snapshot = METRICS.snapshot()
    assert snapshot["offline_cache_hit_rate"] == 0.5
    assert snapshot["offline_dump_age_days"] is not None
    adapter.close()


def test_missing_license_hash_rejected(tmp_path):
    """Дополнение E: без license_file_sha256 дамп не принимается."""
    meta_no_hash = {k: v for k, v in META.items() if k != "license_file_sha256"}
    dump = write_dump(tmp_path / "nohash.jsonl", meta_no_hash,
                      rows=[{"id": "1", "title": "X"}])
    adapter = make_adapter(tmp_path)

    with pytest.raises(OfflineDumpError, match="license_file_sha256"):
        adapter.load(dump)
    adapter.close()


def test_trismegistos_stub_graceful(tmp_path):
    adapter = TrismegistosOfflineAdapter(db_path=str(tmp_path / "offline.db"))

    assert adapter.available is False
    assert adapter.lookup("123") is None
    with pytest.raises(OfflineDumpError, match="no_public_dataset"):
        adapter.load(tmp_path / "anything")
    adapter.close()


def test_registry_lists_adapters():
    available = offline_registry.list_adapters()
    assert "pleiades" in available
    assert "trismegistos" in available


def test_registry_unknown_raises():
    with pytest.raises(KeyError, match="не зарегистрирован"):
        offline_registry.get_adapter("wat")


def test_registry_get_adapter_instance(tmp_path):
    adapter = offline_registry.get_adapter(
        "pleiades", db_path=str(tmp_path / "offline.db")
    )
    assert isinstance(adapter, PleiadesOfflineAdapter)
    adapter.close()


def test_load_large_generated_dump(tmp_path):
    """Устойчивость парсера (уточнение 2.6 №1): 10k записей + edge-cases."""
    big = tmp_path / "big.jsonl"
    with big.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"meta": {**META, "dump_version": "big.1"}}) + "\n")
        for index in range(10_000):
            handle.write(json.dumps({
                "id": str(index),
                "title": f"Place {index}",
                "place_types": (["long"] * 200) if index == 7777 else ["x"],
                "repr_point": None,
                "uri": "",
            }) + "\n")
            if index % 1000 == 0:
                handle.write("\n")  # пустые строки
    adapter = make_adapter(tmp_path)

    result = adapter.load(big)

    assert result["status"] == "loaded"
    assert result["rows"] == 10_000
    assert adapter.lookup("7777").place_types == ["long"] * 200
    with adapter._store._lock:
        names = {
            row[0] for row in adapter._store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
    assert "idx_pleiades_title" in names
    adapter.close()


def test_fixtures_not_gitignored():
    """Уточнение 2.6 №2: tests/fixtures/ не должен ловиться data/*-правилами."""
    import subprocess

    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        ["git", "check-ignore", "tests/fixtures/dumps/pleiades_sample.jsonl"],
        capture_output=True, text=True, cwd=str(repo_root),
    )
    assert proc.returncode != 0, f"fixtures ignored!: {proc.stdout.strip()}"
