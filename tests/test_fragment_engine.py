"""Тесты Fragment Hypothesis Engine (шаг 2.3) — mock, 0 сети."""

import json
from pathlib import Path

from aeon.fragments import (
    DEFAULT_RECONSTRUCT_PROMPT,
    FragmentHypothesisEngine,
)
from aeon.language.grc import AncientGreekPack
from aeon.language.la import LatinPack
from aeon.semantic_atom import SemanticAtom
from aeon.verification.base import Verdict
from aeon.verification.verdicts import (
    VERDICT_ABSTAINED,
    VERDICT_CONTRADICTED,
    VERDICT_GROUNDED,
    VERDICT_UNVERIFIABLE_MISSING_DATA,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class StubVerifier:
    """Заглушка верификатора: detective возвращает заданный вердикт."""

    def __init__(self, verdict: Verdict):
        self._verdict = verdict
        self.detective = self
        self.calls = []

    def verify(self, context):
        self.calls.append(context.claims[0])
        return self._verdict


def make_atom(text: str) -> SemanticAtom:
    return SemanticAtom(meaning_hash="test", source_text=text)


def make_engine(mock_llm, verdict=VERDICT_GROUNDED):
    stub = StubVerifier(Verdict(verdict, 0.9, "detective"))
    engine = FragmentHypothesisEngine(llm_client=mock_llm, verifier=stub)
    return engine, stub


def reconstruct_responses(count=2):
    return {"You reconstruct": {"hypotheses": [
        {"text": f"восстановление-{i + 1}",
         "confidence": round(0.8 - 0.1 * i, 2),
         "evidence": f"контекст-{i + 1}"}
        for i in range(count)
    ], "status": "ok"}}


def test_engine_returns_2_to_4_hypotheses(mock_llm):
    mock_llm.responses = reconstruct_responses(3)
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("ἄειδε θεά [...] πόλις ἐστίν"),
                                pack=AncientGreekPack())

    assert result.status == "ok"
    assert 2 <= len(result.hypotheses) <= 4


def test_engine_returns_no_reconstruction_if_under_threshold(mock_llm):
    mock_llm.responses = {"You reconstruct": {"hypotheses": [
        {"text": "x", "confidence": 0.3, "evidence": "e"},
        {"text": "y", "confidence": 0.2, "evidence": "e"},
    ], "status": "ok"}}
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "no_reconstruction_possible"
    assert result.no_reconstruction.reason == "max_confidence_below_threshold"


def test_engine_caps_at_4(mock_llm):
    mock_llm.responses = reconstruct_responses(5)
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "ok"
    assert len(result.hypotheses) == 4


def test_hypotheses_ranked_descending_by_confidence(mock_llm):
    mock_llm.responses = {"You reconstruct": {"hypotheses": [
        {"text": "low", "confidence": 0.55, "evidence": "e"},
        {"text": "high", "confidence": 0.9, "evidence": "e"},
        {"text": "mid", "confidence": 0.7, "evidence": "e"},
    ], "status": "ok"}}
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    confidences = [h.confidence for h in result.hypotheses]
    assert confidences == sorted(confidences, reverse=True)
    assert result.hypotheses[0].text == "high"


def test_hypothesis_has_evidence_field(mock_llm):
    mock_llm.responses = reconstruct_responses(2)
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    for hypothesis in result.hypotheses:
        assert hypothesis.evidence  # не пустое


def test_engine_uses_pack_markers(mock_llm):
    """Pack-приоритет: маркеры из пака (lacuna + supplement)."""
    mock_llm.responses = reconstruct_responses(2)
    engine, _ = make_engine(mock_llm)
    text = "καὶ [Ἀθῆναι ...] [...] τέλος"

    result = engine.reconstruct(make_atom(text), pack=AncientGreekPack())

    assert result.markers_count >= 2
    addressed = result.hypotheses[0].markers_addressed
    assert "[...]" in addressed
    assert any("[Ἀθῆναι" in token for token in addressed)


def test_engine_fallback_markers_without_pack(mock_llm):
    """Fallback semantic_atom.LACUNA_MARKERS при pack=None."""
    mock_llm.responses = reconstruct_responses(2)
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=None)

    assert result.status == "ok"
    assert result.markers_count == 1


def test_engine_cruces_no_reconstruction(mock_llm):
    """Стоп-точка 2.3 №4: cruces без внешних свидетельств → терминальный отказ."""
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("passage †corruptum† here"), pack=LatinPack())

    assert result.status == "no_reconstruction_possible"
    assert result.no_reconstruction.reason == "cruces_without_external_evidence"
    assert mock_llm.calls == []  # без LLM-вызова


def test_engine_inscription_ig_lacunae(mock_llm):
    mock_llm.responses = reconstruct_responses(3)
    engine, _ = make_engine(mock_llm)
    text = (EXAMPLES / "greek" / "inscription_ig_lacunae.txt").read_text(encoding="utf-8")

    result = engine.reconstruct(make_atom(text), pack=AncientGreekPack())

    assert result.status == "ok"
    assert result.markers_count >= 5


def test_engine_sappho_contested(mock_llm):
    """Sappho: обычный fragment-путь; «варианты чтения» — backlog Ф2.4 (стоп-точка №1)."""
    mock_llm.responses = reconstruct_responses(2)
    engine, _ = make_engine(mock_llm)
    text = (EXAMPLES / "greek" / "sappho_fr31.txt").read_text(encoding="utf-8")

    result = engine.reconstruct(make_atom(text), pack=AncientGreekPack())

    assert result.status == "ok"
    assert len(result.hypotheses) >= 2


def test_fragment_density_computed(mock_llm):
    mock_llm.responses = reconstruct_responses(2)
    engine, _ = make_engine(mock_llm)

    clean = engine.reconstruct(make_atom("полный текст без пропусков"),
                               pack=AncientGreekPack())
    assert clean.markers_count == 0
    assert clean.fragment_density == 0.0
    assert clean.no_reconstruction.reason == "no_markers"

    text = "текст [...] конец"
    fragment = engine.reconstruct(make_atom(text), pack=AncientGreekPack())
    assert fragment.fragment_density == round(1 / len(text), 6)


def test_hypotheses_contradicted_dropped_all(mock_llm):
    mock_llm.responses = reconstruct_responses(3)
    engine, stub = make_engine(mock_llm, verdict=VERDICT_CONTRADICTED)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "no_reconstruction_possible"
    assert result.no_reconstruction.reason == "all_contradicted"
    assert len(stub.calls) == 3  # каждая гипотеза прошла Детектива


def test_hypotheses_pass_detective_each(mock_llm):
    mock_llm.responses = reconstruct_responses(3)
    engine, stub = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "ok"
    assert len(stub.calls) == 3  # N гипотез → N вызовов Детектива (стоп-точка №2)
    assert all(h.verified for h in result.hypotheses)
    assert result.hypotheses[0].verification["verdict"] == VERDICT_GROUNDED


def test_fragment_config_rejects_verify_disabled():
    """Отключение верификации гипотез запрещено (curator fix 2.3)."""
    import pytest

    from aeon.config import ConfigError, FragmentsConfig

    with pytest.raises(ConfigError, match="VERIFY_HYPOTHESES"):
        FragmentsConfig(verify_hypotheses=False)


def test_no_reconstruction_serializable(mock_llm):
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("passage †corruptum†"), pack=LatinPack())

    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "cruces_without_external_evidence" in payload


def test_reconstruction_result_ok_serializable(mock_llm):
    mock_llm.responses = reconstruct_responses(2)
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert payload["status"] == "ok"
    assert payload["hypotheses"][0]["evidence"]


def test_default_prompt_under_30_lines():
    assert DEFAULT_RECONSTRUCT_PROMPT.count("\n") + 1 <= 30


def test_llm_unavailable_returns_no_reconstruction(mock_llm):
    mock_llm.available = False
    engine, _ = make_engine(mock_llm)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "no_reconstruction_possible"
    assert result.no_reconstruction.reason == "llm_unavailable"


def test_engine_sappho_hallucination_rejected(mock_llm):
    """Гипотеза без опоры в source (Детектив neutral) НЕ попадает в финал."""
    mock_llm.responses = reconstruct_responses(2)
    stub = StubVerifier(Verdict(VERDICT_UNVERIFIABLE_MISSING_DATA, 0.4, "detective"))
    engine = FragmentHypothesisEngine(llm_client=mock_llm, verifier=stub)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "no_reconstruction_possible"
    assert result.no_reconstruction.reason == "no_verified_hypotheses"
    assert result.hypotheses == []


def test_engine_hypothesis_requires_detective_grounded(mock_llm):
    """Только grounded проходит; abstained — нет (curator fix 2.3)."""
    mock_llm.responses = reconstruct_responses(2)
    stub = StubVerifier(Verdict(VERDICT_ABSTAINED, 0.0, "detective"))
    engine = FragmentHypothesisEngine(llm_client=mock_llm, verifier=stub)

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "no_reconstruction_possible"
    assert result.no_reconstruction.reason == "no_verified_hypotheses"
    assert len(stub.calls) == 2  # обе гипотезы проверялись


def test_engine_no_verified_hypotheses_returns_no_reconstruction(mock_llm):
    """Смесь neutral + abstained (без contradicted) → no_verified_hypotheses."""
    mock_llm.responses = reconstruct_responses(2)

    class SeqVerifier:
        def __init__(self):
            self.detective = self
            self.calls = []

        def verify(self, context):
            self.calls.append(context.claims[0])
            verdict = (VERDICT_UNVERIFIABLE_MISSING_DATA
                       if len(self.calls) == 1 else VERDICT_ABSTAINED)
            return Verdict(verdict, 0.4, "detective")

    engine = FragmentHypothesisEngine(llm_client=mock_llm, verifier=SeqVerifier())

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.no_reconstruction.reason == "no_verified_hypotheses"


def test_engine_mixed_verdicts_keep_only_grounded(mock_llm):
    """Смесь: grounded проходит, contradicted/neutral отброшены."""
    mock_llm.responses = reconstruct_responses(3)

    class SeqVerifier:
        def __init__(self):
            self.detective = self
            self.calls = []
            self._verdicts = [VERDICT_GROUNDED, VERDICT_CONTRADICTED,
                              VERDICT_UNVERIFIABLE_MISSING_DATA]

        def verify(self, context):
            self.calls.append(context.claims[0])
            return Verdict(self._verdicts.pop(0), 0.9, "detective")

    engine = FragmentHypothesisEngine(llm_client=mock_llm, verifier=SeqVerifier())

    result = engine.reconstruct(make_atom("текст [...] конец"), pack=AncientGreekPack())

    assert result.status == "ok"
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].verification["verdict"] == VERDICT_GROUNDED


def test_fragment_min_confidence_default_075():
    """Порог реконструкции 0.75 — выше abstention верификации (curator fix 2.3)."""
    from aeon.config import CONFIG

    assert CONFIG.fragments.min_confidence == 0.75
