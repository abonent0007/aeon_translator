"""Тесты morph_v1 (шаг 3.2): промпт-контракт + engine completeness + hook."""

from aeon.morphology import MORPH_V1_PROMPT, MorphEngine
from aeon.verification.base import _nfc

GOLD_HOMER_FORMS = ["μῆνιν", "ἄειδε", "θεά", "Πηληϊάδεω", "Ἀχιλῆος"]


def _response(forms):
    return {"forms": forms}


def _entry(index, form, lemma=None, pos="noun", case=None, number=None,
           gender=None, tense=None, mood=None, voice=None, person=None):
    return {"index": index, "form": form, "lemma": lemma or form, "pos": pos,
            "tense": tense, "mood": mood, "voice": voice, "person": person,
            "case": case, "number": number, "gender": gender}


# ── промпт-контракт ──


def test_morph_prompt_contains_enums_and_fixes():
    assert "optative" in MORPH_V1_PROMPT
    assert "mediopassive" in MORPH_V1_PROMPT
    assert "common" in MORPH_V1_PROMPT           # epicene (κύων)
    assert "adjective" in MORPH_V1_PROMPT        # НЕ 'adj'
    assert "ablative" in MORPH_V1_PROMPT
    assert "dual" in MORPH_V1_PROMPT
    assert "1st person singular present indicative" in MORPH_V1_PROMPT  # deponent
    assert "uncontracted" in MORPH_V1_PROMPT     # Attic contraction
    assert "index" in MORPH_V1_PROMPT and "no gaps" in MORPH_V1_PROMPT
    assert "Iliad 2.1-2" in MORPH_V1_PROMPT      # replacement few-shot
    assert "ἄνδρα μοι ἔννεπε" not in MORPH_V1_PROMPT  # Od.1.1 текст убран


# ── engine ──


def test_morph_engine_happy_path(mock_llm):
    mock_llm.responses = {"You perform morphological analysis": _response([
        _entry(1, "μῆνιν", "μῆνις", "noun", case="accusative",
               number="singular", gender="feminine"),
        _entry(2, "ἄειδε", "ἀείδω", "verb", tense="present", mood="imperative",
               voice="active", person=2, number="singular"),
    ])}
    engine = MorphEngine(llm_client=mock_llm)

    result = engine.analyze("μῆνιν ἄειδε", "grc", ["μῆνιν", "ἄειδε"])

    assert [item["form"] for item in result] == ["μῆνιν", "ἄειδε"]
    assert result[0]["case"] == "accusative"
    assert result[1]["mood"] == "imperative"
    assert result[1]["case"] is None


def test_morph_engine_completeness_violation_nulls_missing(mock_llm):
    # LLM вернула только 2 из 3 форм + перепутанный порядок
    mock_llm.responses = {"You perform morphological analysis": _response([
        _entry(2, "θεά", "θεά", "noun", case="vocative", number="singular",
               gender="feminine"),
        _entry(1, "μῆνιν", "μῆνις", "noun", case="accusative",
               number="singular", gender="feminine"),
    ])}
    engine = MorphEngine(llm_client=mock_llm)

    result = engine.analyze("μῆνιν θεά ἄειδε", "grc", ["μῆνιν", "θεά", "ἄειδε"])

    assert len(result) == 3
    assert result[0]["case"] == "accusative"     # sorted by index
    assert result[1]["case"] == "vocative"
    assert result[2]["lemma"] is None            # missing → all-null fallback
    assert result[2]["form"] == "ἄειδε"


def test_morph_engine_parse_error_all_null(mock_llm):
    mock_llm.responses = {}                       # дефолт "{}" → нет forms
    engine = MorphEngine(llm_client=mock_llm)

    result = engine.analyze("μῆνιν", "grc", ["μῆνιν"])

    assert result[0]["form"] == "μῆνιν"
    assert result[0]["lemma"] is None


def test_morph_engine_llm_unavailable():
    class _Offline:
        available = False

    engine = MorphEngine(llm_client=_Offline())
    result = engine.analyze("μῆνιν", "grc", ["μῆνιν"])

    assert result == [{"form": "μῆνιν", "lemma": None, "pos": None, "tense": None,
                       "mood": None, "voice": None, "person": None, "case": None,
                       "number": None, "gender": None}]


def test_morph_engine_empty_forms():
    class _Offline:
        available = False

    assert MorphEngine(llm_client=_Offline()).analyze("x", "grc", []) == []


def test_runner_morph_hook():
    """Hook gold/runner: morph_engine вызывается только на атомах с разметкой."""
    from pathlib import Path

    from aeon.gold import load_dataset
    from aeon.gold.runner import _make_llm, run_dataset

    dataset = load_dataset(Path(__file__).resolve().parent.parent
                           / "gold" / "annotations")
    calls = []

    def stub_engine(text, language, forms):
        calls.append((language, list(forms)))
        return [{"form": form, "lemma": None, "pos": None, "tense": None,
                 "mood": None, "voice": None, "person": None, "case": None,
                 "number": None, "gender": None} for form in forms]

    subset = type(dataset)(records=[r for r in dataset.records
                                    if r.text_id == "homer_iliad_1"][:2],
                           annotations_dir=dataset.annotations_dir)
    predictions = run_dataset(subset, llm=_make_llm("mock", 0.0),
                              morph_engine=stub_engine, with_verdicts=False)

    assert len(calls) == 2, [
        (p.segment_id, p.failed, p.error)
        for p in predictions.get("homer_iliad_1", [])]
    assert calls[0][1] == GOLD_HOMER_FORMS
    homer = predictions["homer_iliad_1"]
    assert len(homer[0].morphology) == 5
    assert homer[0].morphology[0]["form"] == _nfc("μῆνιν")
