"""Тесты Language Pack Infrastructure (шаг 2.0) — 0 сети, только stdlib."""

import unicodedata
from typing import List

import pytest

from aeon.language import registry
from aeon.language.base import LanguagePack, Marker

GREEK_RANGES = ((0x0370, 0x03FF), (0x1F00, 0x1FFF))
LATIN_EXT_RANGES = ((0x0100, 0x017F),)


class MockGreekPack(LanguagePack):
    iso_code = "grc"
    display_name = "Ancient Greek (mock)"
    period = (-800, 600)
    direction = "ltr"
    special_tokens = {"lacuna": "[...]", "editorial": "<...>"}
    prompts = {"extract": "e", "verify": "v", "reconstruct": "r"}
    unicode_ranges = GREEK_RANGES

    def detect_markers(self, text: str) -> List[Marker]:
        return self._markers_from_special_tokens(text)


class MockLatinPack(LanguagePack):
    iso_code = "la"
    display_name = "Latin (mock)"
    period = (-200, 1800)
    special_tokens = {"lacuna": "[...]", "editorial": "<...>"}
    prompts = {"extract": "e", "verify": "v", "reconstruct": "r"}
    unicode_ranges = LATIN_EXT_RANGES

    def detect_markers(self, text: str) -> List[Marker]:
        return self._markers_from_special_tokens(text)


class MockPackNoTokens(LanguagePack):
    iso_code = "xx"
    special_tokens = {"lacuna": "[...]"}  # нет editorial
    prompts = {"extract": "e", "verify": "v", "reconstruct": "r"}

    def detect_markers(self, text: str) -> List[Marker]:
        return self._markers_from_special_tokens(text)


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear()
    yield
    from aeon.language import register_builtins

    registry.clear()
    register_builtins()  # восстановление builtins для последующих тестов


def test_register_and_get():
    registry.register(MockGreekPack)

    pack = registry.get("grc")

    assert isinstance(pack, MockGreekPack)
    assert pack.display_name.startswith("Ancient Greek")


def test_get_unknown_raises_keyerror():
    registry.register(MockGreekPack)

    with pytest.raises(KeyError) as exc_info:
        registry.get("la")

    message = str(exc_info.value)
    assert "la" in message
    assert "grc" in message  # список доступных в сообщении


def test_list_available_sorted():
    registry.register(MockLatinPack)
    registry.register(MockGreekPack)

    assert registry.list_available() == ["grc", "la"]


def test_duplicate_registration_raises():
    registry.register(MockGreekPack)

    with pytest.raises(ValueError, match="уже зарегистрирован"):
        registry.register(MockGreekPack)

    registry.register(MockGreekPack, force=True)  # осознанный override
    assert registry.list_available() == ["grc"]


def test_detect_greek_by_unicode():
    registry.register(MockGreekPack)

    pack = registry.detect("Ἀθῆναι πόλις ἐστίν")

    assert pack is not None
    assert pack.iso_code == "grc"


def test_detect_latin_by_heuristic():
    registry.register(MockLatinPack)

    assert registry.detect("cūrā ut valeās").iso_code == "la"
    # Чистый ASCII не детектируется — ограничение эвристики (док.)
    assert registry.detect("cura ut valeas") is None


def test_detect_unknown_returns_none():
    registry.register(MockGreekPack)

    assert registry.detect("Hello, world!") is None
    assert registry.detect("") is None
    assert registry.detect("   ") is None


def test_abstract_base_not_instantiable():
    with pytest.raises(TypeError):
        LanguagePack()


def test_lazy_loading():
    calls = []

    def factory():
        calls.append("instantiated")
        return MockGreekPack()

    factory.iso_code = "grc"
    registry.register(factory)

    assert calls == []  # регистрация без инстанциации

    registry.get("grc")
    assert calls == ["instantiated"]

    registry.get("grc")  # повторный get — из кеша
    assert calls == ["instantiated"]


def test_special_tokens_contract():
    for pack_class in (MockGreekPack, MockLatinPack):
        pack = pack_class()
        assert "lacuna" in pack.special_tokens
        assert "editorial" in pack.special_tokens
        pack.validate()  # не бросает


def test_validate_missing_keys_raises():
    with pytest.raises(ValueError, match="editorial"):
        MockPackNoTokens().validate()


def test_register_instance_validates_fail_fast():
    with pytest.raises(ValueError, match="editorial"):
        registry.register(MockPackNoTokens())


def test_detect_markers_positions_and_kind():
    pack = MockGreekPack()
    text = "начало [...] и <...> конец"

    markers = pack.detect_markers(text)

    assert [marker.kind for marker in markers] == ["lacuna", "editorial"]
    assert text[markers[0].start:markers[0].end] == "[...]"
    assert text[markers[1].start:markers[1].end] == "<...>"
    assert markers[0].start == len("начало ")
    assert markers[1].start == len("начало [...] и ")


def test_pack_is_fragment_uses_markers():
    pack = MockGreekPack()

    assert pack.is_fragment("текст [...]") is True
    assert pack.is_fragment("полный текст") is False


def test_normalize_default_nfc():
    pack = MockGreekPack()

    composed = "Ἀθῆναι"
    decomposed = unicodedata.normalize("NFD", composed)
    assert decomposed != composed
    assert pack.normalize(decomposed) == composed


def test_detect_tie_resolved_alphabetically(monkeypatch):
    """Tie-break (refinement 2.0 №1): детерминированно — алфавитный iso_code."""
    events = []
    monkeypatch.setattr(
        "aeon.language.registry.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )

    class PackZZ(LanguagePack):
        iso_code = "zz"
        special_tokens = {"lacuna": "[...]", "editorial": "<...>"}
        prompts = {"extract": "e", "verify": "v", "reconstruct": "r"}
        unicode_ranges = GREEK_RANGES

        def detect_markers(self, text):
            return []

    class PackAA(PackZZ):
        iso_code = "aa"

    registry.register(PackZZ)  # зарегистрирован ПЕРВЫМ
    registry.register(PackAA)

    winner = registry.detect("Ἀθῆναι")

    assert winner.iso_code == "aa"  # алфавитный порядок, не порядок регистрации
    ambiguous = [event for event in events if event["msg"] == "detect_ambiguous"]
    assert len(ambiguous) == 1
    assert ambiguous[0]["candidates"] == ["aa", "zz"]


def test_force_override_succeeds():
    class MockGreekPackV2(MockGreekPack):
        display_name = "Ancient Greek (v2)"

    registry.register(MockGreekPack)
    registry.register(MockGreekPackV2, force=True)

    pack = registry.get("grc")

    assert pack.display_name == "Ancient Greek (v2)"
    assert registry.list_available() == ["grc"]


def test_force_override_replaces_lazy_spec():
    calls = []

    def factory():
        calls.append("old")
        return MockGreekPack()

    factory.iso_code = "grc"
    registry.register(factory)

    class MockGreekPackV2(MockGreekPack):
        display_name = "Ancient Greek (v2)"

    registry.register(MockGreekPackV2, force=True)  # фабрика вытеснена

    pack = registry.get("grc")

    assert isinstance(pack, MockGreekPackV2)
    assert calls == []  # старый lazy-инстанс так и не построен
