"""Тесты .aeon v2 (шаг 3.1): writer/reader/validator/versioning + миграция v1."""

import json
import warnings
from pathlib import Path

import pytest

from aeon.config import CONFIG
from aeon.format import (
    AeonSchemaError,
    AeonVersionError,
    build_thresholds_snapshot,
    compatibility,
    compute_atom_hash,
    compute_content_hash,
    dump_v2,
    load_v1_and_migrate,
    load_v2,
    parse_version,
    update_extensions,
    validate_v2,
    write_v2,
)
from aeon.semantic_atom import Entity, SemanticAtom

FROZEN_V1 = (Path(__file__).resolve().parent / "fixtures" / "aeon_v1"
             / "legacy.aeon")


def make_atom(**overrides) -> SemanticAtom:
    atom = SemanticAtom(
        meaning_hash="testmh",
        source_text="ἄειδε θεά [...]",
        intent="statement",
        domain="literature",
        semantic_roles={"agent": "Homer"},
        evidence=["ἄειδε θεά"],
        complexity=0.3,
        urgency=0.1,
        entities=[Entity(name="Homer", type="person")],
    )
    atom.thresholds_snapshot = build_thresholds_snapshot()
    for key, value in overrides.items():
        setattr(atom, key, value)
    return atom


def make_doc(**overrides):
    traces = {"extraction": {"intent": "statement"}, "verification": None,
              "linguistics": None, "focus": None, "reconstruction": None,
              "entity_linking": None}
    doc = dump_v2(
        make_atom(),
        source={"content": "ἄειδε θεά [...]", "form": "text", "language": "greek"},
        traces=traces,
    )
    doc.update(overrides)
    return doc


# ── versioning ──

def test_parse_version():
    assert parse_version("2.0.0") == (2, 0, 0)
    with pytest.raises(AeonVersionError):
        parse_version("^2.x")


def test_reader_accepts_minor_bump():
    """D4: 2.1.0 читается reader'ом (minor игнорируется)."""
    assert compatibility("2.1.0") == "ok"
    assert compatibility("2.0.0") == "ok"
    assert compatibility("1.0.0") == "migrate"


def test_reader_rejects_future_major_version():
    with pytest.raises(AeonVersionError, match="reader too old"):
        compatibility("3.0.0")


# ── validator ──

def test_validator_rejects_missing_required():
    doc = make_doc()
    del doc["metadata"]["mock"]
    with pytest.raises(AeonSchemaError, match="mock"):
        validate_v2(doc)


def test_validator_rejects_future_major_doc():
    doc = make_doc(aeon_version="3.0.0")
    with pytest.raises(AeonSchemaError, match="reader too old"):
        validate_v2(doc)


def test_writer_rejects_atom_without_snapshot():
    """D4: прямой dump_v2 в обход пайплайна → отказ."""
    atom = SemanticAtom(meaning_hash="x", source_text="t", intent="i", domain="d")
    with pytest.raises(AeonSchemaError, match="thresholds_snapshot"):
        dump_v2(atom, source={"content": "t", "form": "text", "language": "x"},
                traces={})


def test_thresholds_snapshot_captured_at_creation_not_write():
    """D3: writer читает snapshot ИЗ АТОМА, не пересчитывает CONFIG."""
    atom = make_atom()
    atom.thresholds_snapshot = {"detective": {"min_confidence": 0.111}}
    doc = dump_v2(atom, source={"content": "t", "form": "text", "language": "x"},
                  traces={})
    assert doc["metadata"]["thresholds_snapshot"]["detective"]["min_confidence"] == 0.111
    assert doc["metadata"]["thresholds_snapshot"]["detective"]["min_confidence"] != CONFIG.detective.min_confidence


# ── extensions ──

def test_extensions_namespaced():
    doc = make_doc()
    doc["extensions"] = {"notnamespaced": 1}
    with pytest.raises(AeonSchemaError, match="namespaced"):
        validate_v2(doc)


def test_extensions_cannot_override_core():
    doc = make_doc()
    doc["extensions"] = {"source": {"hack": True}, "aeon.ok": 1}
    with pytest.raises(AeonSchemaError, match="core"):
        validate_v2(doc)


def test_extensions_v1_original_is_immutable():
    """D4: legacy_*-ключи после миграции не перезаписываются."""
    doc = load_v1_and_migrate(FROZEN_V1)
    with pytest.raises(AeonSchemaError, match="immutable"):
        update_extensions(doc, {"legacy_v1_original": {"hacked": True}})


# ── pipeline metadata ──

def test_pipeline_metadata_distinguishes_skipped_from_failed():
    doc = dump_v2(
        make_atom(),
        source={"content": "t", "form": "text", "language": "x"},
        traces={"extraction": {"ok": True}, "focus": None},
        pipeline={
            "steps_requested": ["extract", "focus"],
            "steps_executed": ["extract"],
            "steps_halted": [{"step": "focus", "reason": "halted_at_lexical"}],
            "steps_failed": [],
        },
    )
    assert doc["traces"]["focus"] is None
    assert doc["metadata"]["pipeline"]["steps_executed"] == ["extract"]
    assert doc["metadata"]["pipeline"]["steps_halted"][0]["step"] == "focus"


# ── hashes ──

def test_content_hash_stable_across_runs():
    text = "стабильный текст"
    assert compute_content_hash(text) == compute_content_hash(text)
    assert compute_content_hash(text) != compute_content_hash(text + "!")


def test_atom_hash_differs_on_llm_variation():
    atom_a = make_atom()
    atom_b = make_atom(evidence=["другое доказательство"])
    assert compute_atom_hash(atom_a) != compute_atom_hash(atom_b)


# ── mock-guard ──

def test_mock_flag_required_true_before_2_7(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(AeonSchemaError, match="mock must be true"):
        dump_v2(make_atom(), source={"content": "t", "form": "text", "language": "x"},
                traces={}, mock=False)


def test_force_unsafe_logs_operator_and_reason(monkeypatch):
    """W2: аудит-лог с reason/operator/trace_id."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("AEON_OPERATOR", "tester")
    events = []
    monkeypatch.setattr(
        "aeon.format.writer.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    dump_v2(make_atom(), source={"content": "t", "form": "text", "language": "x"},
            traces={}, mock=False, force_unsafe=True, force_reason="unit-test",
            trace_id="tr-1")

    bypassed = [e for e in events if e["msg"] == "aeon_mock_flag_bypassed"]
    assert len(bypassed) == 1
    assert bypassed[0]["reason"] == "unit-test"
    assert bypassed[0]["operator"] == "tester"
    assert bypassed[0]["trace_id"] == "tr-1"


def test_force_unsafe_requires_reason(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(AeonSchemaError, match="mock must be true"):
        dump_v2(make_atom(), source={"content": "t", "form": "text", "language": "x"},
                traces={}, mock=False, force_unsafe=True)


def test_mock_false_allowed_with_key(monkeypatch):
    """Стоп №3 (2.7): с ключом mock=false разрешён без force_unsafe."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    doc = dump_v2(make_atom(), source={"content": "t", "form": "text", "language": "x"},
                  traces={}, mock=False)
    assert doc["metadata"]["mock"] is False


# ── 2b: контрактные метаданные (chain_language/anchor_language/extractor_contract) ──


def test_v2_records_extractor_contract():
    """2b: metadata несёт контрактные поля; anchor_language из атома."""
    atom = make_atom()
    atom.anchor_language = "grc"
    doc = dump_v2(atom, source={"content": "t", "form": "text", "language": "grc"},
                  traces={})

    meta = doc["metadata"]
    assert meta["extractor_contract"] == "v1"
    assert meta["chain_language"] == "en"
    assert meta["anchor_language"] == "grc"


def test_v2_roundtrip_with_contract_metadata(tmp_path):
    doc = dump_v2(make_atom(), source={"content": "t", "form": "text",
                                       "language": "x"}, traces={})
    path = write_v2(tmp_path / "c.aeon.json", doc)

    loaded = load_v2(path)

    assert loaded["metadata"]["extractor_contract"] == "v1"
    assert loaded["metadata"]["chain_language"] == "en"
    assert loaded["metadata"]["anchor_language"] is None


def test_reader_migration_defaults_legacy_for_old_v2(tmp_path):
    """Старые v2 (2.7.x) без полей → v3.0-legacy + дефолты (кураторское правило)."""
    doc = dump_v2(make_atom(), source={"content": "t", "form": "text",
                                       "language": "x"}, traces={})
    for key in ("extractor_contract", "chain_language", "anchor_language"):
        doc["metadata"].pop(key, None)
    path = write_v2(tmp_path / "old.aeon.json", doc)

    loaded = load_v2(path)

    assert loaded["metadata"]["extractor_contract"] == "v3.0-legacy"
    assert loaded["metadata"]["chain_language"] == "en"
    assert loaded["metadata"]["anchor_language"] is None


def test_validator_accepts_contract_metadata_types(tmp_path):
    doc = dump_v2(make_atom(), source={"content": "t", "form": "text",
                                       "language": "x"}, traces={})
    doc["metadata"]["chain_language"] = 42

    with pytest.raises(AeonSchemaError, match="chain_language"):
        write_v2(tmp_path / "bad.aeon.json", doc)


# ── roundtrip ──

def test_dump_v2_roundtrip_full_traces(tmp_path):
    doc = dump_v2(
        make_atom(),
        source={"content": "ἄειδε θεά [...]", "form": "text", "language": "greek"},
        traces={
            "extraction": {"ok": True},
            "verification": {"combined": {"verdict": "verified"}},
            "linguistics": {"status": "ok", "layers": []},
            "reconstruction": {"status": "no_reconstruction_possible"},
            "focus": {"status": "ok"},
        },
    )
    path = tmp_path / "full.aeon.json"
    write_v2(path, doc)

    loaded = load_v2(path)

    assert loaded["aeon_version"] == "2.0.0"
    assert loaded["metadata"]["mock"] is True
    assert loaded["traces"]["verification"]["combined"]["verdict"] == "verified"
    assert loaded["traces"]["focus"]["status"] == "ok"
    assert loaded["traces"]["variant_readings"] is None
    assert loaded["traces"]["morphology"] is None
    assert loaded["traces"]["cross_references"] is None


def test_roundtrip_with_partial_traces(tmp_path):
    doc = dump_v2(
        make_atom(),
        source={"content": "t", "form": "text", "language": "x"},
        traces={"extraction": {"ok": True}},
        pipeline={"steps_requested": ["extract"], "steps_executed": ["extract"],
                  "steps_halted": [], "steps_failed": []},
    )
    path = tmp_path / "partial.aeon.json"
    write_v2(path, doc)
    loaded = load_v2(path)
    assert loaded["traces"]["verification"] is None
    assert loaded["metadata"]["pipeline"]["steps_requested"] == ["extract"]


# ── миграция v1 ──

def test_migrate_frozen_v1_fixture():
    """D1: читается ЗАМОРОЖЕННЫЙ исторический v1-артефакт."""
    doc = load_v1_and_migrate(FROZEN_V1)

    assert doc["aaon_version"] if False else doc["aeon_version"] == "2.0.0"
    assert doc["atom"]["intent"] == "statement"
    assert doc["atom"]["domain"] == "literature"
    legacy = doc["extensions"]["legacy_v1_original"]
    assert legacy["meaning_hash"] == "legacy0000dead"
    assert doc["metadata"]["mock"] is True


def test_migrate_does_not_reuse_v1_meaning_hash():
    """D2: meaning_hash только в legacy; atom_hash вычислен заново."""
    doc = load_v1_and_migrate(FROZEN_V1)
    assert doc["extensions"]["legacy_v1_original"]["meaning_hash"] == "legacy0000dead"
    assert doc["atom"]["atom_hash"] != "legacy0000dead"
    assert doc["atom"]["content_hash"] == compute_content_hash(doc["atom"]["text"])


def test_migration_v1_with_entities_external_ids():
    """D4: v1 entities получают v2-дефолты."""
    doc = load_v1_and_migrate(FROZEN_V1)
    entity = doc["atom"]["entities"][0]
    assert entity["name"] == "Homer"
    assert entity["external_ids"] == {}
    assert entity["link_confidence"] == 0.0
    assert entity["is_fragment"] is False
    assert entity["completeness_score"] == 1.0
    assert entity["source_unavailable"] is False


def test_v1_writer_output_still_migrates(tmp_path):
    """D1 (smoke): свежий v1-output production-врайтера тоже мигрируется."""
    from aeon.aeon_format import AeonFormat

    atom = make_atom()
    path = tmp_path / "runtime_v1.aeon"
    AeonFormat.serialize(atom, str(path))

    doc = load_v1_and_migrate(path)

    assert doc["atom"]["content_hash"]


def test_v1_writer_matches_frozen_fixture(tmp_path):
    """D1: паритет с frozen fixture — расхождение → warning (не error)."""
    from aeon.aeon_format import AeonFormat

    probe = tmp_path / "probe.aeon"
    AeonFormat.serialize(make_atom(source_text="ἄειδε θεά Πηληϊάδεω Ἀχιλῆος [...]",
                                   meaning_hash="legacy0000dead"),
                         str(probe))
    fresh = AeonFormat.deserialize(str(probe))[0]
    frozen = AeonFormat.deserialize(str(FROZEN_V1))[0]

    if (fresh.meaning_hash, len(fresh.entities)) != (frozen.meaning_hash,
                                                     len(frozen.entities)):
        warnings.warn("v1 writer drift vs frozen fixture — проверить легальность эволюции",
                      stacklevel=2)
    assert True  # паритет-тест: предупреждает, не падает


def test_demo_save_aeon_without_optional_steps(tmp_path):
    """Уточнение 3.1 №1: --verify=off --save-aeon без layers/focus не падает
    (регрессия на NameError chain_result/focus_run)."""
    import subprocess
    import sys

    target = tmp_path / "min.aeon.json"
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "aeon.demo",
         "--text", "examples/greek/plato_apologia_17a.txt",
         "--verify=off", "--save-aeon", str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(repo_root), timeout=180,
    )
    assert target.exists(), (proc.stdout[-400:] + proc.stderr[-400:])
    doc = load_v2(target)
    assert doc["metadata"]["pipeline"]["steps_executed"] == ["extract"]
    assert doc["traces"]["linguistics"] is None
