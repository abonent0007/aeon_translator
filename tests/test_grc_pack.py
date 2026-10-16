"""Тесты Ancient Greek Pack (шаг 2.1) — 0 сети."""

import unicodedata

import pytest

from aeon.language import registry
from aeon.language.grc import AncientGreekPack

PACK = AncientGreekPack()


@pytest.fixture(autouse=True)
def _grc_registered():
    registry.register(AncientGreekPack, force=True)
    yield
    from aeon.language import register_builtins

    registry.clear()
    register_builtins()  # восстановление builtins для последующих тестов


def test_iso_code_and_metadata():
    assert PACK.iso_code == "grc"
    assert PACK.display_name == "Ancient Greek"
    assert PACK.period == (-800, 600)
    assert PACK.direction == "ltr"
    PACK.validate()


def test_normalize_nfc_and_sigma_policy():
    composed = "σοφία"
    decomposed = unicodedata.normalize("NFD", composed)
    assert PACK.normalize(decomposed) == composed

    # Политика: конечная сигма ς НЕ унифицируется с σ
    assert PACK.normalize("λόγος") == "λόγος"
    assert "ς" in PACK.normalize("λόγος")


def test_normalize_iota_subscript_policy():
    word = "τῇ"  # eta + iota subscript + perispomeni

    normalized = PACK.normalize(word)

    assert normalized == word          # сохраняется как есть
    assert "ι" not in normalized       # НЕ разворачивается в iota adscript
    assert unicodedata.normalize("NFD", word) != normalized  # NFD развернул бы


def test_normalize_preserves_breathing_marks():
    rough = "ἡ"   # грубое дыхание
    smooth = "ἠ"  # тонкое дыхание

    assert PACK.normalize(rough) == rough
    assert PACK.normalize(unicodedata.normalize("NFD", rough)) == rough
    assert PACK.normalize(rough) != PACK.normalize(smooth)  # дыхание семантично


def test_detect_markers_lacuna():
    markers = PACK.detect_markers("текст [...] и далее [---]")

    lacunae = [m for m in markers if m.kind == "lacuna"]
    assert len(lacunae) >= 2


def test_detect_markers_editorial():
    markers = PACK.detect_markers("фрагмент <...> и ещё <*>")

    assert [m.kind for m in markers] == ["editorial", "editorial"]


def test_detect_markers_positions():
    text = "начало [...] конец"

    markers = PACK.detect_markers(text)

    assert text[markers[0].start:markers[0].end] == "[...]"
    assert markers[0].start == len("начало ")


def test_supplement_vs_lacuna_context():
    """Стоп-точка 2.1 №1: [буквы] → supplement, [точки/тире] → lacuna."""
    text = "[Ἀριστ]είδης εἶπεν [...]"

    markers = PACK.detect_markers(text)

    kinds = [m.kind for m in markers]
    assert "supplement" in kinds
    assert "lacuna" in kinds
    supplement = [m for m in markers if m.kind == "supplement"][0]
    assert text[supplement.start:supplement.end] == "[Ἀριστ]"


def test_is_fragment_true_on_lacuna():
    assert PACK.is_fragment("ἔδοξεν τῆι βουλῆι· [...]") is True


def test_is_fragment_false_on_clean():
    assert PACK.is_fragment("μῆνιν ἄειδε θεά") is False


def test_prompts_reference_special_tokens():
    for key in ("extract", "verify", "reconstruct"):
        prompt = PACK.prompts[key]
        assert "[...]" in prompt or "lacuna" in prompt
    assert "no_reconstruction_possible" in PACK.prompts["reconstruct"]
    assert "unverifiable_due_to_missing_data" in PACK.prompts["verify"]


def test_prompts_length_under_30_lines():
    for key, prompt in PACK.prompts.items():
        assert prompt.count("\n") + 1 <= 30, f"промпт {key} длиннее 30 строк"


def test_detect_via_registry():
    pack = registry.detect("ἄειδε θεά")

    assert pack is not None
    assert pack.iso_code == "grc"


def test_registry_lists_grc_after_registration():
    assert "grc" in registry.list_available()


def test_grc_inherits_default_heuristic():
    """grc не переопределяет detect_heuristic — default 0.0 (refinement 2.2 №1)."""
    assert AncientGreekPack().detect_heuristic("μῆνιν ἄειδε θεά") == 0.0


def test_detect_modern_greek_documented_limitation():
    """Новогреческий тоже матчится на grc — известное ограничение (AGENTS.md)."""
    pack = registry.detect("καλημέρα, φίλε")

    assert pack is not None
    assert pack.iso_code == "grc"  # древний/новый не различаем (стоп-точка 2.0 №2)


def test_detective_quote_matches_after_normalization(mock_llm):
    """Quote-matching работает с нормализованным греческим (NFC, диакритика)."""
    from aeon.config import CONFIG
    from aeon.verification import DetectiveAgent, VerificationContext
    from aeon.verification.verdicts import VERDICT_GROUNDED

    mock_llm.responses = {"Detective": {"claims": [
        {"claim": "Ахилл гневается", "quote": "μῆνιν ἄειδε θεά", "contradicts": False,
         "confidence": 0.9, "reasoning": "exact"},
    ]}}

    source = AncientGreekPack().normalize("μῆνιν ἄειδε θεά Πηληϊάδεω Ἀχιλῆος")
    agent = DetectiveAgent(mock_llm, CONFIG.verification.detective)

    verdict = agent.verify(VerificationContext(
        source_text=source, claims=["Ахилл гневается"]
    ))

    assert verdict.verdict == VERDICT_GROUNDED
    quote = verdict.details["claims"][0]["quote"]
    assert quote in source  # диакритика не деградировала — точная подстрока


def test_end_to_end_translate_with_grc_pack(mock_llm, sample_structure):
    from aeon.embeddings import EmbeddingEngine
    from aeon.extractor import MeaningExtractor
    from aeon.generator import ExpressionGenerator
    from aeon.translator import AeonTranslator
    from aeon.verification import VerificationEngine

    def offline_embeddings():
        engine = EmbeddingEngine()
        engine.available = False
        return engine

    mock_llm.responses = {"Analyze the following text": sample_structure}
    translator = AeonTranslator(load_embeddings=False)
    translator.embeddings = offline_embeddings()
    translator.llm = mock_llm
    translator.extractor = MeaningExtractor(
        llm_client=mock_llm, embedding_engine=offline_embeddings()
    )
    translator.generator = ExpressionGenerator(llm_client=mock_llm)
    translator.verification = VerificationEngine(llm_client=mock_llm)
    translator.verification.embeddings = offline_embeddings()

    text = "ἄειδε θεά [...]"
    result = translator.translate(text, source_language="greek",
                                  language_pack=AncientGreekPack())

    assert result["source"]["content"] == text          # оригинал сохранён
    assert result["semantic_atom"].source_text == text  # NFC — без изменений
