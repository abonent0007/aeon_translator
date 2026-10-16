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
    morphology_f1,
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
    assert len(dataset.by_text()) == 15
    assert len(dataset.records) == 54      # expansion 1.1.0 + 3.4 cross-refs (1.2.0)
    assert dataset.version() == "1.2.0"    # mixed 1.0.0/1.1.0/1.2.0 → max версия
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
    assert len(checked.records) == 54


def test_gold_report_dry_run_plan(dataset):
    """Dry-run (2.7.3, стоп №4): план вызовов без API."""
    from aeon.gold.report import planned_calls

    plan = planned_calls(dataset)

    assert plan["extract_calls"] == 54
    assert plan["verdict_records"] == 8      # Plato 3 + Sappho 5 (verdict-тексты)
    assert plan["verify_calls"] == 24
    assert plan["total"] == 78


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


def test_runner_resilient_on_segment_failure(dataset, monkeypatch):
    """Resilience (2.7.3): падение на сегменте НЕ роняет прогон."""
    from aeon.extractor import MeaningExtractor
    from aeon.gold.runner import _make_llm

    subset = type(dataset)(records=[r for r in dataset.records
                                    if r.text_id == "plato_apologia_17a"],
                           annotations_dir=dataset.annotations_dir)
    original = MeaningExtractor.extract_from_text
    state = {"calls": 0}

    def flaky(self, text, source_lang="auto"):
        state["calls"] += 1
        if state["calls"] == 2:
            raise RuntimeError("simulated edge-case")
        return original(self, text, source_lang)

    monkeypatch.setattr(MeaningExtractor, "extract_from_text", flaky)
    llm = _make_llm("mock", 0.0)
    stats = {}

    predictions = run_dataset(subset, llm=llm, stats=stats)

    plato = predictions["plato_apologia_17a"]
    assert len(plato) == 3                      # прогон продолжился
    assert plato[1].failed and "simulated" in plato[1].error
    assert not plato[0].failed and not plato[2].failed
    assert stats["failures"][0]["segment_id"] == 2
    assert stats["per_text"]["plato_apologia_17a"]["calls"] >= 2


# ── schema 1.1.0: morphology infra ──


def _form(form, lemma, pos, case=None, number=None, gender=None, tense=None,
          mood=None, voice=None, person=None):
    return {"form": form, "lemma": lemma, "pos": pos, "tense": tense,
            "mood": mood, "voice": voice, "person": person, "case": case,
            "number": number, "gender": gender}


def test_loader_accepts_1_0_0_and_1_1_0(dataset):
    versions = {r.schema_version for r in dataset.records}
    assert versions == {"1.0.0", "1.1.0", "1.2.0"}   # mixed, включая 3.4
    homer1 = next(r for r in dataset.records
                  if r.text_id == "homer_iliad_1" and r.segment_id == 1)
    assert homer1.expected_morphology and len(homer1.expected_morphology) == 5
    papyrus = next(r for r in dataset.records if r.text_id == "papyrus_oxy")
    assert papyrus.expected_morphology is None
    vergil1 = next(r for r in dataset.records
                   if r.text_id == "vergil_aen_1" and r.segment_id == 1)
    assert len(vergil1.raw.get("expected_cross_references") or []) == 2


def test_loader_excludes_low_confidence(tmp_path):
    records = [_record(annotator="human:test", annotation_confidence="low",
                       segment_id=1, segment_text="ἄειδε θεά"),
               _record(annotator="human:test", segment_id=2, segment_text="σὺν ἄλλοισι")]
    loaded = load_dataset(_write_dataset(tmp_path, records), mode="research")
    assert loaded.records[0].excluded is True
    assert loaded.records[1].excluded is False


def test_morphology_f1_per_field():
    expected = [_form("ἄειδε", "ἀείδω", "verb", tense="present",
                      mood="imperative", voice="active", person=2, number="singular")]
    predicted = [_form("ἄειδε", "ἀείδω", "verb", tense="present",
                       mood="indicative", voice="active", person=2, number="singular")]
    per_field = morphology_f1(expected, predicted, "grc")
    assert per_field["pos"]["f1"] == 1.0
    assert per_field["mood"]["f1"] == 0.0            # imperative != indicative
    assert per_field["tense"]["f1"] == 1.0
    assert per_field["case"]["total"] == 0           # verb: case=None → вне denominator


def test_morphology_f1_denominator_is_subset():
    expected = [_form("μῆνιν", "μῆνις", "noun", case="accusative",
                      number="singular", gender="feminine"),
                _form("ἄειδε", "ἀείδω", "verb", tense="present",
                      mood="imperative", voice="active", person=2,
                      number="singular")]
    predicted = list(expected)                       # все поля верны
    per_field = morphology_f1(expected, predicted, "grc")
    assert per_field["case"]["total"] == 1           # только noun
    assert per_field["pos"]["total"] == 2
    assert per_field["mood"]["total"] == 1           # только verb


def test_morphology_null_fields_excluded_from_denominator():
    # singular для εἰμί-инфинитива = None → number вне denominator
    expected = [_form("ἔμμεναι", "εἰμί", "verb", tense="present",
                      mood="infinitive", voice="active", number=None)]
    predicted = [_form("ἔμμεναι", "εἰμί", "verb", tense="present",
                       mood="infinitive", voice="active", number=None)]
    per_field = morphology_f1(expected, predicted, "grc")
    assert per_field["number"]["total"] == 0
    assert per_field["mood"]["total"] == 1


def test_lemma_matching_nfc_exact():
    import unicodedata
    decomposed = unicodedata.normalize("NFD", "ἀγαθός")
    expected = [_form(decomposed, decomposed, "adjective",
                      case="nominative", number="singular", gender="neuter")]
    predicted = [_form("ἀγαθός", "ἀγαθός", "adjective",
                       case="nominative", number="singular", gender="neuter")]
    per_field = morphology_f1(expected, predicted, "grc")
    assert per_field["lemma"]["f1"] == 1.0           # NFC снимает разложение
    # регистр для grc НЕ фолдится: Ἀγαθός != ἀγαθός
    mismatch = [_form("ἀγαθός", "Ἀγαθός", "adjective")]
    assert morphology_f1(expected, mismatch, "grc")["lemma"]["f1"] == 0.0


def test_lemma_matching_latin_casefold():
    expected = [_form("Catilīna", "Catilīna", "noun", case="vocative",
                      number="singular", gender="masculine")]
    predicted = [_form("Catilīna", "catilīna", "noun", case="vocative",
                       number="singular", gender="masculine")]
    assert morphology_f1(expected, predicted, "la")["lemma"]["f1"] == 1.0


def test_morphology_f1_splits_by_confidence():
    from aeon.gold.loader import GoldDataset, GoldRecord
    from aeon.gold.runner import GoldPrediction
    def make_record(seg_id, confidence):
        return GoldRecord(
            text_id="tiny", language="grc", segment_id=seg_id,
            segment_text="x" * seg_id, schema_version="1.1.0",
            annotator="human:test", annotation_date="2026-10-14",
            expected_atom={"intent": "s", "domain": "l", "is_fragment": False,
                           "completeness_score": 1.0},
            annotation_confidence=confidence,
            expected_morphology=[_form("μῆνιν", "μῆνις", "noun",
                                       case="accusative", number="singular",
                                       gender="feminine")],
        )

    gold = GoldDataset(records=[make_record(1, "high"),
                                make_record(2, "medium")])
    predictions = {"tiny": [
        GoldPrediction("tiny", 1, morphology=[
            _form("μῆνιν", "μῆνις", "noun", case="accusative",
                  number="singular", gender="feminine")]),
        GoldPrediction("tiny", 2, morphology=[
            _form("μῆνιν", "μῆνις", "noun", case="vocative",
                  number="singular", gender="feminine")]),
    ]}

    evaluation = evaluate_dataset(gold, predictions)
    morph = evaluation["per_text"]["tiny"]["morphology"]

    assert morph["high"]["case"]["f1"] == 1.0
    assert morph["medium"]["case"]["f1"] == 0.0
    assert morph["all"]["case"]["total"] == 2


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


def test_metrics_entities_accent_insensitive():
    """Коммит 4: grave/acute-варианты совпадают (сравнение, не вывод)."""
    expected = [{"name": "Διός", "wikidata_id": None, "is_fragment": False},
                {"name": "Ἀκαμαντίς", "wikidata_id": None, "is_fragment": False}]
    predicted = [{"name": "Διὸς", "wikidata_id": None},
                 {"name": "Ἀκαμαντὶς", "wikidata_id": None}]
    assert entities_prf(expected, predicted)["f1"] == 1.0


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


def test_gold_1_1_1_personal_pronouns_have_person(dataset):
    """Class A (1.1.1): личные местоимения несут person; case-фиксы применены."""
    personal = {"ἐγώ": 1, "ἡμεῖς": 1, "nōs": 1, "σύ": 2, "ὑμεῖς": 2, "tū": 2}
    for record in dataset.records:
        for form in (record.expected_morphology or []):
            if form.get("pos") == "pronoun" and form.get("lemma") in personal:
                assert form.get("person") == personal[form["lemma"]], \
                    (record.text_id, form["form"], form.get("person"))
    cicero4 = next(r for r in dataset.records
                   if r.text_id == "cicero_cat_1" and r.segment_id == 4)
    for form in cicero4.expected_morphology:
        if form["form"] in ("nocturnum", "praesidium", "ōra", "vultūs"):
            assert form["case"] == "nominative"
    homer2 = next(r for r in dataset.records
                  if r.text_id == "homer_iliad_1" and r.segment_id == 2)
    eta = next(f for f in homer2.expected_morphology if f["form"] == "ἣ")
    assert eta["case"] == "nominative"


def test_all_gold_artifacts_tracked_in_git():
    """Design principle #15: данные шага обязаны быть в git (кейс 3.4.0)."""
    import subprocess

    if not (REPO / ".git").exists():
        pytest.skip("не git-checkout")
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "gold/"],
        cwd=REPO, capture_output=True, text=True)
    assert result.stdout.strip() == "", \
        f"untracked gold-артефакты: {result.stdout.strip()}"
