"""Тесты Chain-of-Linguistics (шаг 2.4) — mock, 0 сети."""

import pytest

from aeon.config import ConfigError
from aeon.language.grc import AncientGreekPack
from aeon.linguistics import ChainOfLinguistics, Finding, LayerContext, LexicalLayer
from aeon.linguistics.prompts import PROMPTS

LAYER_RESPONSES = {
    "LEXICAL": {"findings": [
        {"kind": "lemma", "value": "μῆνις", "span": [0, 5],
         "confidence": 0.85, "note": ""},
    ], "confidence": 0.82, "handoff": {"lemmas": ["μῆνις"]}},
    "SYNTACTIC": {"findings": [
        {"kind": "pos_tag", "value": "noun", "span": [0, 5],
         "confidence": 0.8, "note": ""},
    ], "confidence": 0.8, "handoff": {"clauses": ["main"]}},
    "SEMANTIC": {"findings": [
        {"kind": "proposition", "value": "пение о гневе",
         "span": None, "confidence": 0.82, "note": ""},
    ], "confidence": 0.82, "handoff": {"propositions": ["p1"]}},
    "PRAGMATIC": {"findings": [
        {"kind": "speech_act", "value": "invocation",
         "span": None, "confidence": 0.8, "note": ""},
    ], "confidence": 0.8, "handoff": {"speech_acts": ["invocation"]}},
}

TEXT = "μῆνιν ἄειδε θεά"


def make_chain(mock_llm):
    return ChainOfLinguistics(llm_client=mock_llm)


def run_chain(mock_llm, layers, pack=None, text=TEXT):
    mock_llm.responses = dict(LAYER_RESPONSES)
    chain = make_chain(mock_llm)
    return chain.run(text, layers=layers, pack=pack, trace_id="t-1")


def halted_chain(mock_llm):
    mock_llm.responses = dict(LAYER_RESPONSES)
    mock_llm.responses["LEXICAL"] = {**LAYER_RESPONSES["LEXICAL"], "confidence": 0.2}
    chain = make_chain(mock_llm)
    return chain.run(TEXT, layers=["all"], trace_id="t-1")


def _prompt_of(mock_llm, marker):
    for call in mock_llm.calls:
        content = call["messages"][-1]["content"]
        if marker in content:
            return content
    return None


def test_lexical_standalone(mock_llm):
    result = run_chain(mock_llm, ["lexical"])

    assert result.status == "ok"
    assert [layer.layer for layer in result.layers] == ["lexical"]
    assert result.llm_calls == 1


def test_syntactic_requires_lexical(mock_llm):
    chain = make_chain(mock_llm)

    with pytest.raises(ConfigError, match="lexical"):
        chain.validate_layers(["syntactic"])


def test_semantic_requires_syntactic(mock_llm):
    chain = make_chain(mock_llm)

    with pytest.raises(ConfigError, match="syntactic"):
        chain.run(TEXT, layers=["lexical", "semantic"])


def test_pragmatic_requires_semantic(mock_llm):
    chain = make_chain(mock_llm)

    with pytest.raises(ConfigError, match="semantic"):
        chain.validate_layers(["pragmatic"])


def test_unknown_layer_raises(mock_llm):
    chain = make_chain(mock_llm)

    with pytest.raises(ConfigError, match="Неизвестные слои"):
        chain.validate_layers(["morphology"])


def test_chain_handoff_preserved(mock_llm):
    result = run_chain(mock_llm, ["lexical", "syntactic"])

    assert result.status == "ok"
    syntactic_prompt = _prompt_of(mock_llm, "SYNTACTIC")
    assert syntactic_prompt is not None
    assert "PREVIOUS LAYER OUTPUT (lexical)" in syntactic_prompt
    assert "μῆνις" in syntactic_prompt  # handoff лексики передан синтаксису


def test_chain_trace_id_shared(mock_llm):
    result = run_chain(mock_llm, ["all"])

    assert result.trace_id == "t-1"
    assert all(layer.trace_id == "t-1" for layer in result.layers)


def test_all_layers_4_llm_calls(mock_llm):
    result = run_chain(mock_llm, ["all"])

    assert result.status == "ok"
    assert result.llm_calls == 4


def test_llm_budget_recorded_on_halt(mock_llm):
    result = halted_chain(mock_llm)

    assert result.llm_calls == 1  # цепочка остановилась после lexical


def test_layer_confidence_propagates_halt(mock_llm):
    result = halted_chain(mock_llm)

    assert result.status == "halted_at_lexical"


def test_halt_returns_partial_result(mock_llm):
    result = halted_chain(mock_llm)

    assert len(result.layers) == 1
    assert result.layers[0].findings  # частичный результат сохранён


def test_prompt_length_under_30_lines():
    for name, prompt in PROMPTS.items():
        assert prompt.count("\n") + 1 <= 30, f"промпт {name} длиннее 30 строк"


def test_pack_linguistic_hints_injected(mock_llm):
    run_chain(mock_llm, ["lexical"], pack=AncientGreekPack())

    lexical_prompt = _prompt_of(mock_llm, "LEXICAL")
    assert "Ancient Greek specifics" in lexical_prompt
    assert "optative" in lexical_prompt


def test_no_pack_no_hints(mock_llm):
    run_chain(mock_llm, ["lexical"], pack=None)

    lexical_prompt = _prompt_of(mock_llm, "LEXICAL")
    assert "LANGUAGE-SPECIFIC HINTS" not in lexical_prompt


def test_contradiction_detection_logged(mock_llm, monkeypatch):
    events = []
    monkeypatch.setattr(
        "aeon.linguistics.orchestrator.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    mock_llm.responses = {
        "LEXICAL": {"findings": [
            {"kind": "pos_tag", "value": "verb", "span": [0, 5],
             "confidence": 0.85, "note": ""},
        ], "confidence": 0.82, "handoff": {"lemmas": ["x"]}},
        "SYNTACTIC": {"findings": [
            {"kind": "pos_tag", "value": "noun", "span": [0, 5],
             "confidence": 0.8, "note": ""},
        ], "confidence": 0.8, "handoff": {"clauses": ["main"]}},
    }
    chain = make_chain(mock_llm)

    result = chain.run(TEXT, layers=["lexical", "syntactic"], trace_id="t-1")

    conflicts = [event for event in events if event["msg"] == "layer_contradiction"]
    assert len(conflicts) == 1
    assert conflicts[0]["conflicts"][0]["kind"] == "pos_tag"
    syntactic = result.layers[1]
    assert syntactic.confidence == round(0.8 * 0.7, 4)  # мягкое понижение (вариант B)
    assert syntactic.handoff["contradictions"]


def test_finding_and_layers_serializable(mock_llm):
    import json

    result = run_chain(mock_llm, ["lexical"])

    payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert payload["layers"][0]["findings"][0]["kind"] == "lemma"


def test_lexical_layer_direct_call(mock_llm):
    """Слой можно вызвать напрямую с LayerContext (интерфейс analyze)."""
    mock_llm.responses = dict(LAYER_RESPONSES)
    layer = LexicalLayer(mock_llm)

    result = layer.analyze(LayerContext(
        original_text=TEXT, normalized_text=TEXT, trace_id="t-2",
    ))

    assert isinstance(result.findings[0], Finding)
    assert result.trace_id == "t-2"
    assert result.handoff["lemmas"] == ["μῆνις"]


def test_lexical_syntactic_contradiction_actually_triggers(mock_llm, monkeypatch):
    """Явный триггер: lexical=verb vs syntactic=noun по одному span (curator 2.4)."""
    events = []
    monkeypatch.setattr(
        "aeon.linguistics.orchestrator.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    mock_llm.responses = {
        "LEXICAL": {"findings": [
            {"kind": "pos_tag", "value": "verb", "span": [0, 5],
             "confidence": 0.85, "note": ""},
        ], "confidence": 0.82, "handoff": {"lemmas": ["x"]}},
        "SYNTACTIC": {"findings": [
            {"kind": "pos_tag", "value": "noun", "span": [0, 5],
             "confidence": 0.8, "note": ""},
        ], "confidence": 0.8, "handoff": {"clauses": ["main"]}},
    }
    chain = ChainOfLinguistics(llm_client=mock_llm)

    result = chain.run(TEXT, layers=["lexical", "syntactic"], trace_id="t-1")

    conflict_events = [e for e in events if e["msg"] == "layer_contradiction"]
    assert conflict_events, "детектор обязан сработать на verb vs noun"
    assert result.layers[1].confidence == round(0.8 * 0.7, 4)


def test_handoff_truncation_logged(mock_llm, monkeypatch):
    """Handoff >1500 символов: truncate + событие handoff_truncated (2.4 suspicion #2)."""
    events = []
    monkeypatch.setattr(
        "aeon.linguistics.base.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    big_handoff = {"lemmas": ["λ" * 40] * 60}  # JSON заметно >1500 символов
    mock_llm.responses = {
        "LEXICAL": {"findings": [], "confidence": 0.8, "handoff": big_handoff},
        "SYNTACTIC": {"findings": [
            {"kind": "pos_tag", "value": "noun", "span": [0, 5],
             "confidence": 0.8, "note": ""},
        ], "confidence": 0.8, "handoff": {}},
    }
    chain = ChainOfLinguistics(llm_client=mock_llm)

    chain.run(TEXT, layers=["lexical", "syntactic"], trace_id="t-1")

    truncated = [e for e in events if e["msg"] == "handoff_truncated"]
    assert len(truncated) == 1
    assert truncated[0]["original_len"] > 1500
    syntactic_prompt = _prompt_of(mock_llm, "SYNTACTIC")
    assert "λ" * 40 in syntactic_prompt  # данные дошли (усечённо)
