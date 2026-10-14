"""Тесты Variant Readings (шаг 3.5) — mock, 0 сети (25 тестов)."""

import json
from pathlib import Path

import pytest

from aeon.config import ConfigError
from aeon.variants import (
    ApparatusError,
    ReadingSelector,
    SELECT_READING_PROMPT,
    VariantEngine,
    load_apparatus,
)
from aeon.variants.apparatus import Locus, Reading, work_tokens
from aeon.verification.base import Verdict
from aeon.verification.verdicts import (
    VERDICT_CONTRADICTED,
    VERDICT_GROUNDED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
)

SAPPHO = (Path(__file__).resolve().parent.parent / "examples" / "apparatus"
          / "sappho_fr31.json")


def base_apparatus_dict():
    return {
        "work": "Sappho fr. 31",
        "apparatus_version": "1.0.0",
        "editions": ["Voigt 1971", "Diehl 1925"],
        "loci": [{
            "line": 13,
            "context": "…τὸ δὲ λέπτον δ᾽ αὔτικα χρῶι πῦρ ὐπαδεδρόμηκεν…",
            "readings": [
                {"text": "ἴδρως κακχέεται", "editions": ["Voigt 1971"]},
                {"text": "τρόμος δὲ παῖσαν ἄγρει", "editions": ["Diehl 1925"]},
            ],
        }],
    }


def write_apparatus(tmp_path, payload) -> Path:
    path = tmp_path / "apparatus.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class StubDetective:
    """veto_texts — подстроки claim'ов, которые объявляются contradicted."""

    def __init__(self, veto_texts=None, verdict="grounded"):
        self.veto_texts = set(veto_texts or [])
        self.calls = []
        self._grounded = verdict == "grounded"

    def verify(self, context, mode=""):
        self.calls.append({"claims": list(context.claims),
                            "mode": mode or getattr(context, "mode", "")})
        claim = context.claims[0] if context.claims else ""
        if any(text in claim for text in self.veto_texts):
            return Verdict(VERDICT_CONTRADICTED, 0.9, "detective")
        if self._grounded:
            return Verdict(VERDICT_GROUNDED, 0.9, "detective")
        return Verdict(VERDICT_UNVERIFIABLE_MISSING_DATA, 0.4, "detective")


class StubVerifier:
    def __init__(self, detective):
        self.detective = detective


def make_selector(mock_llm, detective=None, min_confidence=None):
    detective = detective or StubDetective()
    selector = ReadingSelector(mock_llm, StubVerifier(detective),
                               min_confidence=min_confidence)
    return selector, detective


def make_locus(context="some surviving context", texts=("Aaa bbb", "Ccc ddd")):
    editions = ["Voigt 1971", "Diehl 1925"]
    return Locus(line=1, context=context,
                 readings=[Reading(text=texts[0], editions=[editions[0]]),
                           Reading(text=texts[1], editions=[editions[1]])])


# ── apparatus parser ──

def test_apparatus_parser_valid():
    apparatus = load_apparatus(SAPPHO)

    assert apparatus.work == "Sappho fr. 31"
    assert apparatus.apparatus_version == "1.0.0"
    assert [locus.line for locus in apparatus.loci] == [1, 13]
    assert len(apparatus.editions) == 3


def test_apparatus_parser_rejects_reading_without_edition(tmp_path):
    payload = base_apparatus_dict()
    payload["loci"][0]["readings"][0]["editions"] = []
    path = write_apparatus(tmp_path, payload)

    with pytest.raises(ApparatusError, match="ATTRIBUTION"):
        load_apparatus(path)


def test_apparatus_parser_rejects_unknown_edition(tmp_path):
    payload = base_apparatus_dict()
    payload["loci"][0]["readings"][1]["editions"] = ["Unknown 1900"]
    path = write_apparatus(tmp_path, payload)

    with pytest.raises(ApparatusError, match="неизвестное издание"):
        load_apparatus(path)


def test_apparatus_parser_rejects_single_reading_locus(tmp_path):
    payload = base_apparatus_dict()
    payload["loci"][0]["readings"] = payload["loci"][0]["readings"][:1]
    path = write_apparatus(tmp_path, payload)

    with pytest.raises(ApparatusError, match="минимум 2"):
        load_apparatus(path)


def test_apparatus_version_semver_required(tmp_path):
    payload = base_apparatus_dict()
    payload["apparatus_version"] = "1.0"
    path = write_apparatus(tmp_path, payload)

    with pytest.raises(ApparatusError, match="semver"):
        load_apparatus(path)


def test_empty_loci_rejected_by_loader(tmp_path):
    """Уточнение №2 (3.5): apparatus без locus не валиден — нечего выбирать."""
    payload = base_apparatus_dict()
    payload["loci"] = []
    path = write_apparatus(tmp_path, payload)

    with pytest.raises(ApparatusError, match="непустой список"):
        load_apparatus(path)


# ── selector ──

def test_selector_unanimous_no_llm(mock_llm):
    selector, detective = make_selector(mock_llm)
    editions = ["Voigt 1971", "Diehl 1925"]
    locus = Locus(line=1, context="ctx", readings=[
        Reading(text="same text", editions=[editions[0]]),
        Reading(text="same text", editions=[editions[1]]),
    ])

    selection = selector.select(locus, trace_id="t")

    assert selection.status == "unanimous"
    assert selection.llm_calls == 0
    assert mock_llm.calls == []
    assert detective.calls == []
    assert set(selection.editions_support) == set(editions)  # attribution сохранена


def test_selector_unanimous_after_veto_no_llm(mock_llm):
    selector, detective = make_selector(mock_llm, StubDetective(
        veto_texts=["Ccc ddd"]))
    locus = make_locus()

    selection = selector.select(locus)

    assert selection.status == "unanimous_after_veto"
    assert selection.chosen is not None
    assert selection.chosen.text == "Aaa bbb"
    assert selection.llm_calls == 0
    assert mock_llm.calls == []
    assert len(detective.calls) == 2  # обе readings проверены


def test_selector_all_vetoed_no_selection(mock_llm):
    selector, _ = make_selector(mock_llm, StubDetective(
        veto_texts=["Aaa bbb", "Ccc ddd"]))

    selection = selector.select(make_locus())

    assert selection.status == "no_selection_possible"
    assert selection.chosen is None
    assert mock_llm.calls == []
    assert set(selection.editions_vetoed) == {"Aaa bbb", "Ccc ddd"}


def test_selector_chooses_between_two(mock_llm):
    mock_llm.responses = {"select ONE": {
        "chosen_index": 0, "confidence": 0.78, "reasoning": "grammar fits"}}
    selector, _ = make_selector(mock_llm)

    selection = selector.select(make_locus())

    assert selection.status == "selected"
    assert selection.chosen is not None
    assert selection.chosen.text == "Aaa bbb"
    assert selection.confidence == 0.78
    assert selection.editions_support == ["Voigt 1971"]


def test_selector_confidence_below_threshold(mock_llm):
    mock_llm.responses = {"select ONE": {
        "chosen_index": 0, "confidence": 0.4, "reasoning": "weak"}}
    selector, _ = make_selector(mock_llm)

    selection = selector.select(make_locus())

    assert selection.status == "no_selection_possible"
    assert "low_confidence" in selection.reasoning


def test_selector_no_context(mock_llm):
    selector, detective = make_selector(mock_llm)

    selection = selector.select(make_locus(context=""))

    assert selection.status == "no_selection_possible"
    assert "пустой контекст" in selection.reasoning
    assert mock_llm.calls == []
    assert detective.calls == []


def test_selector_uses_detective_prefilter(mock_llm):
    mock_llm.responses = {"select ONE": {
        "chosen_index": 0, "confidence": 0.8, "reasoning": "ok"}}
    selector, detective = make_selector(mock_llm, StubDetective(
        veto_texts=["Ccc ddd"]))

    selection = selector.select(make_locus())

    # veto → осталось 1 → селектор не вызывался (unanimous_after_veto), 0 LLM
    assert selection.llm_calls == 0
    assert selection.status == "unanimous_after_veto"
    assert len(detective.calls) == 2
    assert all(c["mode"] == "reading" for c in detective.calls)


def test_selector_indeterminate_returns_no_selection(mock_llm):
    mock_llm.responses = {"select ONE": {
        "chosen_index": -1, "confidence": 0.0, "reasoning": "tied"}}
    selector, _ = make_selector(mock_llm)

    selection = selector.select(make_locus())

    assert selection.status == "no_selection_possible"
    assert selection.confidence == 0.0


def test_selector_prompt_length_under_30_lines():
    assert SELECT_READING_PROMPT.count("\n") + 1 <= 30


def test_selector_prompt_forbids_generation():
    assert "Do NOT generate new text" in SELECT_READING_PROMPT


def test_selector_prompt_hides_editions(mock_llm):
    mock_llm.responses = {"select ONE": {
        "chosen_index": 1, "confidence": 0.8, "reasoning": "ok"}}
    selector, _ = make_selector(mock_llm)

    selector.select(make_locus())

    prompt = mock_llm.calls[-1]["messages"][-1]["content"]
    assert "Voigt" not in prompt
    assert "Diehl" not in prompt
    assert "0: Aaa bbb" in prompt and "1: Ccc ddd" in prompt


def test_selector_rule3_fewer_editorial_marks(mock_llm):
    """Доработка промпта: измеримое правило 3 + честный fallback -1."""
    assert "FEWER editorial marks" in SELECT_READING_PROMPT
    assert "chosen_index: -1" in SELECT_READING_PROMPT
    assert "fewest assumptions" not in SELECT_READING_PROMPT
    assert "does NOT include the locus itself" in SELECT_READING_PROMPT


# ── engine ──

def test_engine_multiple_loci(tmp_path, mock_llm):
    payload = base_apparatus_dict()
    loci = []
    for line_number in (1, 2, 3):
        locus = json.loads(json.dumps(payload["loci"][0]))  # независимая копия
        locus["line"] = line_number
        loci.append(locus)
    payload["loci"] = loci
    apparatus = load_apparatus(write_apparatus(tmp_path, payload))
    mock_llm.responses = {"select ONE": {
        "chosen_index": 0, "confidence": 0.8, "reasoning": "ok"}}
    engine = VariantEngine(llm_client=mock_llm,
                           verifier=StubVerifier(StubDetective()))

    result = engine.run(atom=None, apparatus=apparatus, trace_id="t-1")

    assert len(result.selections) == 3
    assert result.llm_calls == 3


def test_engine_partial_selection(tmp_path, mock_llm):
    payload = base_apparatus_dict()
    payload["loci"].append({
        "line": 2, "context": "",
        "readings": [
            {"text": "Xx yy", "editions": ["Voigt 1971"]},
            {"text": "Zz ww", "editions": ["Diehl 1925"]},
        ],
    })
    apparatus = load_apparatus(write_apparatus(tmp_path, payload))
    mock_llm.responses = {"select ONE": {
        "chosen_index": 0, "confidence": 0.8, "reasoning": "ok"}}
    engine = VariantEngine(llm_client=mock_llm,
                           verifier=StubVerifier(StubDetective()))

    result = engine.run(None, apparatus)

    statuses = [selection.status for selection in result.selections]
    assert statuses == ["selected", "no_selection_possible"]


def test_work_mismatch_plato_apologia_vs_republic(tmp_path, mock_llm):
    """Уточнение №1: общий токен 'Платон' есть, работа другая → ConfigError."""
    payload = base_apparatus_dict()
    payload["work"] = "Plato Apologia"
    apparatus = load_apparatus(write_apparatus(tmp_path, payload))
    engine = VariantEngine(llm_client=mock_llm,
                           verifier=StubVerifier(StubDetective()))

    with pytest.raises(ConfigError, match="work mismatch"):
        engine.run(None, apparatus, work_hint="plato_republic_1")


def test_work_match_passes(tmp_path, mock_llm):
    payload = base_apparatus_dict()
    payload["work"] = "Plato Apologia"
    apparatus = load_apparatus(write_apparatus(tmp_path, payload))
    mock_llm.responses = {"select ONE": {
        "chosen_index": 0, "confidence": 0.8, "reasoning": "ok"}}
    engine = VariantEngine(llm_client=mock_llm,
                           verifier=StubVerifier(StubDetective()))

    result = engine.run(None, apparatus, work_hint="plato_apologia_17a")

    assert len(result.selections) == 1


def test_work_tokens_helper():
    assert work_tokens("Plato Apologia") == {"plato", "apologia"}
    assert work_tokens("Sappho fr. 31") == {"sappho"}


def test_engine_empty_loci_returns_empty_selection(mock_llm):
    """Уточнение №2 (3.5): engine не падает на пустом loci (путь не из loader)."""
    from aeon.variants.apparatus import Apparatus

    apparatus = Apparatus(work="Empty Work", editions=["Ed 2000"],
                          loci=[], apparatus_version="1.0.0")
    engine = VariantEngine(llm_client=mock_llm,
                           verifier=StubVerifier(StubDetective()))

    result = engine.run(None, apparatus)

    assert result.selections == []
    assert result.llm_calls == 0
    assert mock_llm.calls == []


def test_unanimous_after_veto_preserves_vetoed_editions(mock_llm):
    """Уточнение №2 (c): editions_support — выбранного; vetoed — с изданиями."""
    selector, _ = make_selector(mock_llm, StubDetective(veto_texts=["Ccc ddd"]))

    selection = selector.select(make_locus())

    assert selection.status == "unanimous_after_veto"
    assert selection.editions_support == ["Voigt 1971"]
    assert selection.editions_vetoed == {"Ccc ddd": ["Diehl 1925"]}


# ── v2 integration (unit-level, без полного pipeline) ──

def test_v2_trace_variant_readings_filled(tmp_path, mock_llm):
    from aeon.format import build_thresholds_snapshot, dump_v2, load_v2, write_v2
    from aeon.semantic_atom import SemanticAtom

    payload = base_apparatus_dict()
    apparatus = load_apparatus(write_apparatus(tmp_path, payload))
    mock_llm.responses = {"select ONE": {
        "chosen_index": 1, "confidence": 0.8, "reasoning": "ok"}}
    engine = VariantEngine(llm_client=mock_llm,
                           verifier=StubVerifier(StubDetective()))
    variant_result = engine.run(None, apparatus).to_dict()

    atom = SemanticAtom(meaning_hash="t", source_text="s", intent="i", domain="d")
    atom.thresholds_snapshot = build_thresholds_snapshot()
    doc = dump_v2(
        atom, source={"content": "s", "form": "text", "language": "greek"},
        traces={"variant_readings": variant_result},
        pipeline={"steps_requested": ["extract", "variant_readings"],
                  "steps_executed": ["extract", "variant_readings"],
                  "steps_halted": [], "steps_failed": []},
    )
    path = tmp_path / "v2.aeon.json"
    write_v2(path, doc)

    loaded = load_v2(path)
    assert loaded["traces"]["variant_readings"]["work"] == "Sappho fr. 31"
    assert "variant_readings" in loaded["metadata"]["pipeline"]["steps_executed"]


def test_variant_readings_serializable(tmp_path, mock_llm):
    payload = base_apparatus_dict()
    apparatus = load_apparatus(write_apparatus(tmp_path, payload))
    mock_llm.responses = {"select ONE": {
        "chosen_index": 0, "confidence": 0.8, "reasoning": "ok"}}
    engine = VariantEngine(llm_client=mock_llm,
                           verifier=StubVerifier(StubDetective()))

    result = engine.run(None, apparatus, trace_id="t-9")

    payload_json = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert payload_json["trace_id"] == "t-9"
    assert payload_json["selections"][0]["status"] == "selected"


# ── translator-level integration (шаг 1.9) ──

TEXT_WITH_LACUNA = "…τὸ δὲ λέπτον [...] κἄμ' ἴδρως κακχέεται…"


def _translator(mock_llm):
    from aeon.embeddings import EmbeddingEngine
    from aeon.extractor import MeaningExtractor
    from aeon.generator import ExpressionGenerator
    from aeon.translator import AeonTranslator
    from aeon.verification import VerificationEngine

    structure = {
        "intent": "statement", "domain": "poetry",
        "entities": [], "semantic_roles": {}, "evidence": ["…"],
        "explanation_chain": ["строка 13 повреждена (лакуна)"],
        "confidence_breakdown": {}, "complexity": 0.4, "urgency": 0.1,
        "extraction_confidence": 0.8, "semantic_tokens": [],
    }
    mock_llm.responses = {
        "Analyze the following text": structure,
        "You reconstruct": {"hypotheses": []},  # терминальный llm_returned_none
        "select ONE": {"chosen_index": 0, "confidence": 0.8, "reasoning": "ok"},
    }

    def offline_embeddings():
        engine = EmbeddingEngine()
        engine.available = False
        return engine

    instance = AeonTranslator(load_embeddings=False)
    instance.embeddings = offline_embeddings()
    instance.llm = mock_llm
    instance.extractor = MeaningExtractor(llm_client=mock_llm,
                                          embedding_engine=offline_embeddings())
    instance.generator = ExpressionGenerator(llm_client=mock_llm)
    instance.verification = VerificationEngine(llm_client=mock_llm)
    instance.verification.embeddings = offline_embeddings()
    return instance


def test_reconstruct_and_variant_sequential(mock_llm):
    """Фиксированный порядок 3.5: reconstruct (1.6) → variant (1.9)."""
    translator_instance = _translator(mock_llm)

    result = translator_instance.translate(
        TEXT_WITH_LACUNA, source_language="greek",
        reconstruct=True, variant_readings=str(SAPPHO),
    )

    assert result["metadata"]["reconstruction"] is not None
    assert result["variant_readings"] is not None
    assert result["variant_readings"]["llm_calls"] == 2  # два locus

    prompts = [call["messages"][-1]["content"] for call in mock_llm.calls]
    reconstruct_index = next(i for i, p in enumerate(prompts)
                             if "You reconstruct" in p)
    select_index = next(i for i, p in enumerate(prompts) if "select ONE" in p)
    assert reconstruct_index < select_index


def test_backward_compat_no_variant_flag(mock_llm):
    """Без флага variant_readings — поведение Ф3.1 без изменений."""
    translator_instance = _translator(mock_llm)

    result = translator_instance.translate(TEXT_WITH_LACUNA,
                                           source_language="greek")

    assert result["variant_readings"] is None
    assert result["metadata"]["reconstruction"] is None
