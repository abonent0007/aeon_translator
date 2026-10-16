"""Тесты 3.4.1: cross-ref schema (fail-fast), invariant #9, pair-F1 метрика."""

import json
from pathlib import Path

import pytest

from aeon.gold import GoldError, evaluate_dataset, load_dataset
from aeon.gold.loader import GoldDataset, GoldRecord
from aeon.gold.metrics import cross_ref_prf
from aeon.gold.runner import GoldPrediction

REPO = Path(__file__).resolve().parent.parent
ANNOTATIONS = REPO / "gold" / "annotations"

PROEM = {"label": "proem_invocation", "description": "sing-verb + subject-of-song"}


def _form(form, lemma, pos="noun"):
    return {"form": form, "lemma": lemma, "pos": pos, "tense": None, "mood": None,
            "voice": None, "person": None, "case": None, "number": None, "gender": None}


def _xref(kind="adaptation", confidence="high", formula=None, pairs=None,
          source=("tiny", 1), target=("tiny", 2)):
    ref = {"source": {"text_id": source[0], "segment_id": source[1]},
           "target": {"text_id": target[0], "segment_id": target[1]},
           "kind": kind, "confidence": confidence,
           "matched_lemma_pairs": pairs or [],
           "annotator_notes": "test"}
    if formula is not None:
        ref["matched_formula"] = formula
    return ref


def _record(seg_id, text, morph=None, xrefs=None):
    return {"schema_version": "1.2.0", "text_id": "tiny", "language": "grc",
            "segment_id": seg_id, "segment_text": text,
            "marker_offsets_relative_to": "segment",
            "annotator": "human:test", "annotation_date": "2026-10-14",
            "annotation_confidence": "high",
            "expected_atom": {"intent": "statement", "domain": "literature",
                              "is_fragment": False, "completeness_score": 1.0},
            "expected_markers": [], "expected_entities": [],
            "expected_verdicts": None,
            "expected_morphology": morph or [],
            "expected_cross_references": xrefs or []}


def _write(tmp_path, records):
    annotations = tmp_path / "annotations"
    annotations.mkdir(exist_ok=True)
    texts = tmp_path / "texts"
    texts.mkdir(exist_ok=True)
    (texts / "tiny.txt").write_text(
        "\n".join(r["segment_text"] for r in records) + "\n", encoding="utf-8")
    (annotations / "tiny.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8")
    return annotations


def _valid_pair():
    return [{"source_lemma": "μῆνις", "target_lemma": "ἀείδω"}]


def _valid_records():
    return [
        _record(1, "μῆνιν ἄειδε", morph=[_form("μῆνιν", "μῆνις")]),
        _record(2, "θεὰ ἄειδε", morph=[_form("ἄειδε", "ἀείδω", "verb")],
                xrefs=[_xref(pairs=_valid_pair())]),
    ]


# ── fail-fast контракты ──


def test_cross_ref_requires_matched_formula_for_echo(tmp_path):
    records = _valid_records()
    records[1]["expected_cross_references"] = [
        _xref(kind="formulaic_echo", pairs=_valid_pair())]  # без formula
    with pytest.raises(GoldError, match="formulaic_echo требует"):
        load_dataset(_write(tmp_path, records))


def test_cross_ref_formula_label_in_enum(tmp_path):
    records = _valid_records()
    records[1]["expected_cross_references"] = [
        _xref(kind="formulaic_echo",
              formula={"label": "homeric_invocation", "description": "x"},
              pairs=_valid_pair())]
    with pytest.raises(GoldError, match="formula_labels"):
        load_dataset(_write(tmp_path, records))


def test_cross_ref_confidence_in_enum(tmp_path):
    records = _valid_records()
    records[1]["expected_cross_references"] = [_xref(confidence="certain")]
    with pytest.raises(GoldError, match="confidence"):
        load_dataset(_write(tmp_path, records))


def test_cross_ref_kind_in_enum(tmp_path):
    records = _valid_records()
    records[1]["expected_cross_references"] = [_xref(kind="translation")]
    with pytest.raises(GoldError, match="kind"):
        load_dataset(_write(tmp_path, records))


def test_cross_ref_pairs_within_segments(tmp_path):
    records = _valid_records()
    records[1]["expected_cross_references"] = [
        _xref(pairs=[{"source_lemma": "WRONG", "target_lemma": "ἀείδω"}])]
    with pytest.raises(GoldError, match="invariant #9"):
        load_dataset(_write(tmp_path, records))


def test_valid_cross_ref_dataset_loads(tmp_path):
    dataset = load_dataset(_write(tmp_path, _valid_records()))
    assert len(dataset.xrefs) == 1
    assert dataset.xrefs[0]["kind"] == "adaptation"


# ── метрика ──


def test_pair_f1_per_kind():
    ref_a = _xref(kind="adaptation")
    ref_b = _xref(kind="formulaic_echo", formula=PROEM)
    result = cross_ref_prf([ref_a, ref_b], [ref_a])
    assert result["per_kind"]["adaptation"]["f1"] == 1.0
    assert result["per_kind"]["formulaic_echo"]["f1"] == 0.0
    assert result["macro_f1"] == 0.5


def _gold_record(seg_id, xrefs):
    return GoldRecord(
        text_id="tiny", language="grc", segment_id=seg_id,
        segment_text="x" * seg_id, schema_version="1.2.0",
        annotator="human:test", annotation_date="2026-10-14",
        expected_atom={"intent": "s", "domain": "l", "is_fragment": False,
                       "completeness_score": 1.0},
        cross_references=xrefs, expected_morphology=[], excluded=False)


def test_pair_f1_confidence_splits_and_low_excluded():
    ref_high = _xref(confidence="high", source=("tiny", 1), target=("tiny", 2))
    # medium — ДРУГОЙ kind (иначе та же неориентированная пара схлопнется)
    ref_medium = _xref(kind="formulaic_echo", formula=PROEM, confidence="medium",
                       source=("tiny", 1), target=("tiny", 2))
    ref_low = _xref(confidence="low", source=("tiny", 1), target=("tiny", 2))
    gold = GoldDataset(records=[_gold_record(1, [ref_high, ref_low]),
                                _gold_record(2, [ref_medium])])
    predictions = {"tiny": [
        GoldPrediction("tiny", 1, cross_refs=[ref_high]),
        GoldPrediction("tiny", 2, cross_refs=[ref_low, ref_medium]),
    ]}

    evaluation = evaluate_dataset(gold, predictions)
    xref = evaluation["aggregate"]["cross_references"]

    assert xref["high"]["per_kind"]["adaptation"]["tp"] == 1        # high совпал
    assert xref["medium"]["per_kind"]["formulaic_echo"]["tp"] == 1  # medium совпал
    # low исключён из ВСЕХ бакетов: в "all" только 2 записи (high+medium)
    total_all = sum(entry["tp"] + entry["fn"]
                    for entry in xref["all"]["per_kind"].values())
    assert total_all == 2
    assert evaluation["aggregate"]["xref_present"] is True


def test_vergil_real_two_echo_xrefs():
    dataset = load_dataset(ANNOTATIONS)
    vergil_refs = [ref for ref in dataset.xrefs
                   if ref["owner_text_id"] == "vergil_aen_1"]
    assert len(vergil_refs) == 2
    assert {ref["kind"] for ref in vergil_refs} == {"formulaic_echo"}
    assert {ref["confidence"] for ref in vergil_refs} == {"medium", "high"}
    # odyssey-xref указывает на seg1 (clarification 3.4.0)
    odyssey_ref = next(ref for ref in vergil_refs
                       if ref["source"]["text_id"] == "odyssey_1")
    assert odyssey_ref["source"]["segment_id"] == 1
