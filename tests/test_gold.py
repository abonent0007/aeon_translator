"""Тесты gold-standard harness (шаг 3.3) — mock, 0 сети (кроме gold_real)."""

import json
from pathlib import Path

import pytest

from aeon.gold import GoldError, evaluate_dataset, load_dataset, run_dataset
from aeon.gold.metrics import (
    completeness_mae,
    entities_prf,
    is_fragment_accuracy,
    markers_prf,
    verdict_accuracy,
)
from aeon.gold.report import build_report

REPO = Path(__file__).resolve().parent.parent
GOLD = REPO / "gold"
ANNOTATIONS = GOLD / "annotations"


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(ANNOTATIONS)


@pytest.fixture(scope="module")
def mock_predictions(dataset):
    return run_dataset(dataset, mode="mock")


@pytest.fixture(scope="module")
def mock_evaluation(dataset, mock_predictions):
    return evaluate_dataset(dataset, mock_predictions)


# ── helpers ──


def _record(**overrides):
    base = {
        "schema_version": "1.0.0", "text_id": "tiny", "language": "grc",
        "segment_id": 1, "segment_text": "ἄειδε θεά",
        "marker_offsets_relative_to": "segment",
        "annotator": "human:test", "annotation_date": "2026-10-14",
        "expected_atom": {"intent": "statement", "domain": "literature",
                          "is_fragment": False, "completeness_score": 1.0},
        "expected_markers": [], "expected_entities": [], "expected_verdicts": None,
    }
    base.update(overrides)
    return base


def _write_dataset(tmp_path, records, text="ἄειδε θεά σὺν ἄλλοισι\n"):
    annotations = tmp_path / "annotations"
    annotations.mkdir()
    texts = tmp_path / "texts"
    texts.mkdir()
    (texts / "tiny.txt").write_text(text, encoding="utf-8")
    (annotations / "tiny.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8")
    return annotations


# ── loader ──


def test_loader_valid_dataset(dataset):
    assert len(dataset.by_text()) == 6
    assert len(dataset.records) == 28
    assert dataset.version() == "1.0.0"
    assert all(r.annotator.startswith("human:") for r in dataset.records)


def test_loader_rejects_missing_required_fields(tmp_path):
    record = _record()
    del record["expected_atom"]
    with pytest.raises(GoldError, match="ожидают|отсутствуют"):
        load_dataset(_write_dataset(tmp_path, [record]))


def test_loader_rejects_mock_annotator_in_ci(tmp_path):
    annotations = _write_dataset(tmp_path, [_record(annotator="mock")])
    with pytest.raises(GoldError, match="mock"):
        load_dataset(annotations, mode="ci")
    assert load_dataset(annotations, mode="research").records  # research — допустимо


def test_loader_rejects_segment_not_in_text(tmp_path):
    with pytest.raises(GoldError, match="не найдена"):
        load_dataset(_write_dataset(tmp_path, [_record(segment_text="нет такого")]))


def test_loader_rejects_bad_marker_offset(tmp_path):
    record = _record(expected_markers=[
        {"kind": "lacuna", "text": "[...]", "offset": 3}])
    with pytest.raises(GoldError, match="offset"):
        load_dataset(_write_dataset(tmp_path, [record]))


def test_loader_rejects_overlapping_segments(tmp_path):
    records = [
        _record(segment_id=1, segment_text="ἄειδε θεά"),
        _record(segment_id=2, segment_text="θεά σὺν"),
    ]
    with pytest.raises(GoldError, match="перекрыва"):
        load_dataset(_write_dataset(tmp_path, records))


def test_segment_texts_non_overlapping(dataset):
    """Сегменты одного текста не перекрываются (offset-матчинг маркеров)."""
    for text_id, records in dataset.by_text().items():
        full_text = (GOLD / "texts" / f"{text_id}.txt").read_text(encoding="utf-8")
        spans = sorted((full_text.find(r.segment_text),
                        full_text.find(r.segment_text) + len(r.segment_text))
                       for r in records)
        for (_, end), (start, _) in zip(spans, spans[1:]):
            assert start >= end, text_id


def test_gold_offsets_tool_and_dataset_valid():
    """Утилита tools/annotate_offsets.py: offset-finder + полная валидация."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "annotate_offsets", REPO / "tools" / "annotate_offsets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rows = module.find_offsets(GOLD / "texts" / "inscription_ig.txt", "[...]")
    assert rows and rows[0][0] == 2   # вхождение в строке 2 декрета
    assert rows[0][1] > 0             # offset внутри строки-сегмента

    checked = module.check_dataset(ANNOTATIONS)
    assert len(checked.records) == 28


def test_gold_report_dry_run_plan(dataset):
    """Dry-run (2.7.3, стоп №4): план вызовов без API."""
    from aeon.gold.report import planned_calls

    plan = planned_calls(dataset)

    assert plan["extract_calls"] == 28
    assert plan["verdict_records"] == 8      # Plato 3 + Sappho 5
    assert plan["verify_calls"] == 24
    assert plan["total"] == 52


def test_cost_block_formats_zero():
    from aeon.gold.report import format_cost_block

    block = format_cost_block({"calls": 0, "latency_sec": 0.0}, {})

    assert "cost: $0.0000" in block
    assert "LLM-вызовов: 0" in block


def test_runner_raw_recorder(tmp_path, dataset):
    """Аудит real-прогонов: сырые ответы пишутся в llm_calls.jsonl."""
    from aeon.gold.runner import _make_llm, attach_raw_recorder

    subset = type(dataset)(records=[r for r in dataset.records
                                    if r.text_id == "plato_apologia_17a"],
                           annotations_dir=dataset.annotations_dir)
    llm = _make_llm("mock", 0.0)
    path = attach_raw_recorder(llm, tmp_path / "raw")

    run_dataset(subset, llm=llm, with_verdicts=False)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3  # 3 сегмента = 3 extract-вызова
    payload = json.loads(lines[0])
    assert "raw" in payload and "messages" in payload


# ── metrics ──


def test_metrics_markers_perfect_match():
    markers = [{"kind": "lacuna", "text": "[...]", "offset": 4}]
    assert markers_prf(markers, markers)["macro_f1"] == 1.0


def test_metrics_markers_partial_match():
    expected = [{"kind": "lacuna", "text": "[...]", "offset": 0},
                {"kind": "lacuna", "text": "[---]", "offset": 10}]
    predicted = [{"kind": "lacuna", "text": "xxxxx", "offset": 1},   # overlap → tp
                 {"kind": "supplement", "text": "[abc]", "offset": 10}]  # kind mismatch
    result = markers_prf(expected, predicted)
    assert result["per_kind"]["lacuna"]["precision"] == 1.0
    assert result["per_kind"]["lacuna"]["recall"] == 0.5
    assert result["per_kind"]["lacuna"]["f1"] == round(2 / 3, 4)
    assert result["per_kind"]["supplement"]["f1"] == 0.0
    assert result["macro_f1"] == round((round(2 / 3, 4) + 0.0) / 2, 4)


def test_metrics_entities_exact_qid():
    expected = [{"name": "Σωκράτης", "wikidata_id": "Q913", "is_fragment": False}]
    predicted = [{"name": "Socrates", "wikidata_id": "Q913"}]
    assert entities_prf(expected, predicted)["f1"] == 1.0


def test_metrics_entities_null_qid_text_match():
    expected = [{"name": "Ἀθηναῖοι", "wikidata_id": None, "is_fragment": False}]
    predicted = [{"name": "ἀθηναῖοι", "wikidata_id": "Q999"}]  # casefold-match
    assert entities_prf(expected, predicted)["f1"] == 1.0
    predicted_wrong = [{"name": "Belgae", "wikidata_id": "Q999"}]
    assert entities_prf(expected, predicted_wrong)["f1"] == 0.0


def test_metrics_is_fragment_accuracy():
    assert is_fragment_accuracy([(True, True), (False, True)]) == 0.5
    assert is_fragment_accuracy([]) == 1.0


def test_metrics_completeness_mae():
    assert completeness_mae([(1.0, 0.6), (1.0, 1.0)]) == 0.2
    assert completeness_mae([]) == 0.0


def test_metrics_verdict_accuracy():
    gold = {"detective": "grounded", "expert": "unverifiable_due_to_missing_data",
            "logician": "coherent"}
    predicted = {"detective": "unverifiable_due_to_missing_data",
                 "expert": "unverifiable_due_to_missing_data",
                 "logician": "coherent"}
    result = verdict_accuracy([(gold, predicted)])
    assert result == {"detective": 0.0, "expert": 1.0, "logician": 1.0}


# ── runner / report ──


def test_runner_pipeline_on_gold(dataset, mock_predictions):
    assert set(mock_predictions.keys()) == set(dataset.by_text().keys())
    for text_id, records in dataset.by_text().items():
        assert len(mock_predictions[text_id]) == len(records)
    plato = mock_predictions["plato_apologia_17a"]
    assert all(p.markers == [] for p in plato)          # чистый текст
    assert all(p.verdicts is not None for p in plato)   # gold ожидает вердикты
    assert plato[0].entities                          # canned fixture entities


def test_runner_mock_not_circular(mock_evaluation, mock_predictions):
    """Фикстура mocks НЕ совпадает с gold: идеальных совпадений нет."""
    aggregate = mock_evaluation["aggregate"]
    assert aggregate["entities"]["f1"] < 1.0, "mock не должен идеально совпадать с gold"
    assert aggregate["completeness_mae"] > 0.0, "canned-структура неполна by design"
    # канned-сущности глобальны и не привязаны к текстам
    names = {e["name"] for e in mock_predictions["homer_iliad_1"][0].entities}
    assert "Belgae" in names  # бельги в Гомере — очевидная нерелевантность (by design)


def test_report_markdown_structure(dataset, mock_predictions):
    report = build_report(dataset, mock_predictions)
    assert "## Aggregate" in report
    assert "## Per text" in report
    assert "Markers macro F1" in report
    assert "Entities F1" in report


# ── pytest-маркеры: baseline (stop №3: reports vs meets_baseline) ──


@pytest.mark.gold_mock
def test_gold_mock_reports_values(mock_evaluation):
    """Всегда проходит: печатает/фиксирует фактические значения."""
    aggregate = mock_evaluation["aggregate"]
    print(f"\n[gold] markers macro F1={aggregate['markers']['macro_f1']} "
          f"entities F1={aggregate['entities']['f1']} "
          f"frag_acc={aggregate['is_fragment_accuracy']} "
          f"MAE={aggregate['completeness_mae']}")
    assert "markers" in aggregate


@pytest.mark.gold_mock
def test_gold_mock_markers_meet_baseline(mock_evaluation):
    aggregate = mock_evaluation["aggregate"]
    assert aggregate["markers"]["macro_f1"] >= 0.9
    assert aggregate["is_fragment_accuracy"] >= 0.9


@pytest.mark.gold_mock
@pytest.mark.xfail(strict=False, reason="mock: canned-фикстура нерелевантна текстам; "
                                        "реальная цель — real-режим (2.7)")
def test_gold_mock_entities_meet_baseline(mock_evaluation):
    assert mock_evaluation["aggregate"]["entities"]["f1"] >= 0.75


@pytest.mark.gold_mock
@pytest.mark.xfail(strict=False, reason="mock: canned-структура неполна (0.6); "
                                        "реальная цель — real-режим (2.7)")
def test_gold_mock_completeness_meet_baseline(mock_evaluation):
    assert mock_evaluation["aggregate"]["completeness_mae"] <= 0.15


@pytest.mark.gold_real
def test_gold_real_plato_smoke(dataset):
    """gold_real: минимальный прогон (Plato, 3 сегмента, без verdicts)."""
    from aeon.llm_client import DeepSeekClient

    llm = DeepSeekClient()
    if not llm.available:
        pytest.skip("DEEPSEEK_API_KEY отсутствует — gold_real пропущен")

    subset = type(dataset)(records=[r for r in dataset.records
                                    if r.text_id == "plato_apologia_17a"],
                           annotations_dir=dataset.annotations_dir)
    predictions = run_dataset(subset, llm=llm, with_verdicts=False)
    assert len(predictions["plato_apologia_17a"]) == 3
