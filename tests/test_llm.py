"""Тесты LLM-слоя (aeon/llm): фасад DeepSeekClient, провайдер, логирование."""

import pytest

from aeon.llm.base import LLMError
from aeon.llm.deepseek import DeepSeekClient
from aeon.llm.openai_compatible import OpenAICompatibleProvider


class FakeStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"http {status_code}")
        self.status_code = status_code


class FakeCompletion:
    def __init__(self, content):
        self.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": content})()})()
        ]


class FakeCompletions:
    def __init__(self, owner):
        self.owner = owner

    def create(self, *, model, messages, temperature, max_tokens, **kwargs):
        self.owner.calls.append(
            {"model": model, "messages": messages,
             "temperature": temperature, "max_tokens": max_tokens}
        )
        if self.owner.errors:
            raise self.owner.errors.pop(0)
        content = self.owner.contents.pop(0) if self.owner.contents else "{}"
        return FakeCompletion(content)


class FakeOpenAI:
    """Минимальная замена openai.OpenAI — 0 реальной сети."""

    def __init__(self, contents=None, errors=None):
        self.contents = list(contents or [])
        self.errors = list(errors or [])
        self.calls = []
        self.chat = type("Chat", (), {"completions": FakeCompletions(self)})()


@pytest.fixture
def captured_events(monkeypatch):
    """Перехватывает log_event внутри провайдера — для проверки контракта логов."""
    events = []
    monkeypatch.setattr(
        "aeon.llm.openai_compatible.log_event",
        lambda logger, msg, **kw: events.append({"msg": msg, **kw}),
    )
    return events


def test_backward_compat_import():
    """Старый путь импорта из v3.0 продолжает работать."""
    from aeon.llm import DeepSeekClient as PkgClient
    from aeon.llm_client import DeepSeekClient as ShimClient

    assert ShimClient is PkgClient


def test_client_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = DeepSeekClient()
    assert client.available is False
    assert client._call([{"role": "user", "content": "hi"}]) == ""
    assert client._call_json([{"role": "user", "content": "hi"}]) == {}


def test_provider_chat_success_logs_event(captured_events):
    fake = FakeOpenAI(contents=["hello"])
    provider = OpenAICompatibleProvider(
        api_key="k", client=fake, name="deepseek", model="m1", trace_id="t-1"
    )

    out = provider.chat([{"role": "user", "content": "hi"}])

    assert out == "hello"
    assert len(captured_events) == 1
    event = captured_events[0]
    assert event["msg"] == "llm_call"
    assert event["provider"] == "deepseek"
    assert event["model"] == "m1"
    assert event["retries"] == 0
    assert event["attempts"] == 1
    assert event["ok"] is True
    assert event["trace_id"] == "t-1"
    assert isinstance(event["latency_ms"], float)


def test_provider_retries_on_5xx(captured_events):
    fake = FakeOpenAI(contents=["ok"], errors=[FakeStatusError(500), FakeStatusError(503)])
    slept = []
    provider = OpenAICompatibleProvider(
        api_key="k", client=fake, sleep=slept.append, base_delay=0.5, max_attempts=3
    )

    out = provider.chat([{"role": "user", "content": "hi"}])

    assert out == "ok"
    assert len(fake.calls) == 3
    assert slept == [0.5, 1.0]
    retry_events = [e for e in captured_events if e["msg"] == "llm_retry"]
    call_events = [e for e in captured_events if e["msg"] == "llm_call"]
    assert len(retry_events) == 2
    assert len(call_events) == 1
    assert call_events[0]["attempts"] == 3
    assert call_events[0]["retries"] == 2
    assert call_events[0]["ok"] is True


def test_provider_4xx_fails_fast(captured_events):
    fake = FakeOpenAI(errors=[FakeStatusError(400)])
    provider = OpenAICompatibleProvider(api_key="k", client=fake, sleep=lambda _: None)

    with pytest.raises(LLMError):
        provider.chat([{"role": "user", "content": "hi"}])

    assert len(fake.calls) == 1
    call_events = [e for e in captured_events if e["msg"] == "llm_call"]
    assert call_events[0]["ok"] is False
    assert call_events[0]["retries"] == 0


def test_facade_call_json_repairs_fences():
    fake = FakeOpenAI(contents=['```json\n{"intent": "question",}\n```'])
    client = DeepSeekClient(client=fake)

    assert client.available is True
    data = client._call_json([{"role": "user", "content": "x"}])
    assert data == {"intent": "question"}


def test_facade_call_json_garbage_returns_parse_error():
    fake = FakeOpenAI(contents=["I cannot do that."])
    client = DeepSeekClient(client=fake)

    data = client._call_json([{"role": "user", "content": "x"}])
    assert data["parse_error"] == "unrepairable JSON"
    assert data["raw_response"] == "I cannot do that."


def test_facade_high_level_method_passthrough():
    fake = FakeOpenAI(contents=["Привет!"])
    client = DeepSeekClient(client=fake)

    result = client.translate_text("Hello", "english", "russian")
    assert result == "Привет!"
    sent = fake.calls[0]["messages"]
    assert any("Translate" in m["content"] for m in sent)


def test_facade_extract_meaning_json():
    fake = FakeOpenAI(contents=['{"intent": "statement", "domain": "general"}'])
    client = DeepSeekClient(client=fake)

    data = client.extract_meaning("Смысл един.")
    assert data["intent"] == "statement"
    assert data["domain"] == "general"
