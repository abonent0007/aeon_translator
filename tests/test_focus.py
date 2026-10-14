"""Тесты Multi-focus (шаг 2.5) — mock, 0 сети."""

import time

import pytest

from aeon.config import ConfigError
from aeon.focus import (
    EsotericRole,
    HistorianRole,
    LinguistRole,
    MultiFocusOrchestrator,
    PhilosopherRole,
    FocusContext,
    aggregate,
)
from aeon.focus.base import FocusAnalysis, Insight
from aeon.focus.prompts import PROMPTS
from aeon.semantic_atom import SemanticAtom

ROLE_RESPONSES = {
    "HISTORIAN": {"insights": [
        {"claim": "Илиада сложилась в VIII веке до н.э.",
         "angle": "historical_context", "confidence": 0.7, "source_refs": ["Q6691"]},
    ], "confidence": 0.7, "evidence": ["эпическая традиция"]},
    "PHILOSOPHER": {"insights": [
        {"claim": "Гнев Ахилла — тема этической ответственности",
         "angle": "philosophical", "confidence": 0.65, "source_refs": []},
    ], "confidence": 0.65, "evidence": ["концепт μῆνις"]},
    "LINGUIST": {"insights": [
        {"claim": "Формула μῆνιν ἄειδε — наследие устной традиции",
         "angle": "language_history", "confidence": 0.75, "source_refs": []},
    ], "confidence": 0.75, "evidence": ["формульность"]},
    "ESOTERIC": {"insights": [], "confidence": 0.3,
                 "evidence": ["нет исторически засвидетельствованной символики"]},
}

TEXT = "μῆνιν ἄειδε θεά"


def make_orchestrator(mock_llm):
    return MultiFocusOrchestrator(llm_client=mock_llm)


def make_atom() -> SemanticAtom:
    return SemanticAtom(meaning_hash="t", source_text=TEXT)


def _prompt_of(mock_llm, marker):
    for call in mock_llm.calls:
        content = call["messages"][-1]["content"]
        if marker in content:
            return content
    return None


def test_role_historian_basic(mock_llm):
    mock_llm.responses = dict(ROLE_RESPONSES)
    analysis = HistorianRole(mock_llm).analyze(FocusContext(atom=make_atom(), trace_id="t-1"))

    assert analysis.role == "historian"
    assert analysis.insights[0].angle == "historical_context"
    assert analysis.trace_id == "t-1"


def test_role_philosopher_basic(mock_llm):
    mock_llm.responses = dict(ROLE_RESPONSES)
    analysis = PhilosopherRole(mock_llm).analyze(FocusContext(atom=make_atom()))

    assert analysis.role == "philosopher"
    assert analysis.insights[0].confidence == 0.65


def test_role_linguist_basic(mock_llm):
    mock_llm.responses = dict(ROLE_RESPONSES)
    analysis = LinguistRole(mock_llm).analyze(FocusContext(atom=make_atom()))

    assert analysis.role == "linguist"
    assert "устной традиции" in analysis.insights[0].claim


def test_role_esoteric_basic(mock_llm):
    mock_llm.responses = dict(ROLE_RESPONSES)
    analysis = EsotericRole(mock_llm).analyze(FocusContext(atom=make_atom()))

    assert analysis.role == "esoteric"
    assert analysis.insights == []  # пустой список — валидный ответ
    assert analysis.evidence


def test_prompts_do_not_leak_between_roles(mock_llm):
    """Стоп-точка №3: историк не видит эзотерику и наоборот."""
    mock_llm.responses = dict(ROLE_RESPONSES)
    make_orchestrator(mock_llm).run(make_atom(), roles=["historian", "esoteric"],
                                    trace_id="t-1")

    historian_prompt = _prompt_of(mock_llm, "HISTORIAN")
    esoteric_prompt = _prompt_of(mock_llm, "ESOTERIC")
    assert "ESOTERIC" not in historian_prompt
    assert "HISTORIAN" not in esoteric_prompt
    assert "esoteric" not in historian_prompt.lower()
    assert "numerology" in esoteric_prompt  # guardrail на месте


def test_roles_run_independently(mock_llm):
    """FocusContext не содержит чужих результатов (структурно)."""
    context = FocusContext(atom=make_atom())

    assert not hasattr(context, "others")
    assert not hasattr(context, "results")
    mock_llm.responses = dict(ROLE_RESPONSES)
    result = make_orchestrator(mock_llm).run(make_atom(), roles=["historian", "philosopher"])
    assert set(result.insights_by_role) == {"historian", "philosopher"}


def test_orchestrator_parallel_when_multiple(mock_llm):
    """3 роли × 300ms: параллельно ≈0.3s, sequential было бы ≈0.9s."""
    mock_llm.responses = dict(ROLE_RESPONSES)
    mock_llm.latency_ms = 300

    started = time.perf_counter()
    result = make_orchestrator(mock_llm).run(
        make_atom(), roles=["historian", "philosopher", "linguist"], trace_id="t-1",
    )
    elapsed = time.perf_counter() - started

    assert result.status == "ok"
    assert len(result.roles) == 3
    assert elapsed < 0.75, f"последовательный прогон? elapsed={elapsed:.2f}s"


def test_orchestrator_sequential_when_one(mock_llm):
    mock_llm.responses = dict(ROLE_RESPONSES)

    result = make_orchestrator(mock_llm).run(make_atom(), roles=["historian"])

    assert result.llm_calls == 1
    assert len(result.roles) == 1


def test_aggregator_preserves_all_insights():
    analyses = [
        FocusAnalysis(role="historian", insights=[Insight(claim="h1")]),
        FocusAnalysis(role="philosopher", insights=[Insight(claim="p1"), Insight(claim="p2")]),
    ]

    result = aggregate(analyses)

    assert len(result.insights_by_role["historian"]) == 1
    assert len(result.insights_by_role["philosopher"]) == 2
    assert result.llm_calls == 2


def test_aggregator_flags_disagreement():
    analyses = [
        FocusAnalysis(role="historian", insights=[
            Insight(claim="Илиада написана в VIII веке до н.э."),
        ]),
        FocusAnalysis(role="philosopher", insights=[
            Insight(claim="Илиада написана в III веке до н.э."),
        ]),
    ]

    result = aggregate(analyses)

    assert result.all_disagree is True


def test_aggregator_no_false_disagreement():
    analyses = [
        FocusAnalysis(role="historian", insights=[Insight(claim="Илиада написана в VIII веке до н.э.")]),
        FocusAnalysis(role="philosopher", insights=[Insight(claim="Гнев Ахилла — этическая тема")]),
    ]

    assert aggregate(analyses).all_disagree is False


def test_focus_unknown_role_raises(mock_llm):
    with pytest.raises(ConfigError, match="Неизвестные роли"):
        make_orchestrator(mock_llm).validate_roles(["shaman"])


def test_focus_all_excludes_esoteric(mock_llm):
    """Стоп-точка №1: 'all' = historian+philosopher+linguist; esoteric — только явно."""
    mock_llm.responses = dict(ROLE_RESPONSES)

    result = make_orchestrator(mock_llm).run(make_atom(), roles=["all"])

    assert set(result.insights_by_role) == {"historian", "philosopher", "linguist"}
    assert "esoteric" not in result.insights_by_role


def test_focus_trace_id_shared(mock_llm):
    mock_llm.responses = dict(ROLE_RESPONSES)

    result = make_orchestrator(mock_llm).run(
        make_atom(), roles=["historian", "philosopher"], trace_id="t-9",
    )

    assert result.trace_id == "t-9"
    assert all(analysis.trace_id == "t-9" for analysis in result.roles)


def test_prompts_length_under_30_lines():
    for name, prompt in PROMPTS.items():
        assert prompt.count("\n") + 1 <= 30, f"промпт {name} длиннее 30 строк"


def test_esoteric_prompt_guardrails():
    prompt = PROMPTS["esoteric"]
    assert "no numerology" in prompt.lower()
    assert "no hidden codes" in prompt.lower()
    assert "attested" in prompt.lower()


def test_multi_focus_result_serializable(mock_llm):
    import json

    mock_llm.responses = dict(ROLE_RESPONSES)
    result = make_orchestrator(mock_llm).run(make_atom(), roles=["historian"])

    payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert payload["insights_by_role"]["historian"][0]["angle"] == "historical_context"
