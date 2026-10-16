"""Token/cost tracking (2.7.7) — stub-клиент, 0 сети."""

from types import SimpleNamespace

from aeon.llm.openai_compatible import OpenAICompatibleProvider
from aeon.llm_client import DeepSeekClient


class _StubCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._responses.pop(0)


def _response(content, prompt_tokens, completion_tokens, usage=True, cache=None,
              finish=None):
    usage_obj = None
    if usage:
        fields = {"prompt_tokens": prompt_tokens,
                  "completion_tokens": completion_tokens}
        if cache is not None:  # Note 4: поле может отсутствовать
            fields["prompt_cache_hit_tokens"] = cache
        usage_obj = SimpleNamespace(**fields)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content),
                                 finish_reason=finish)],
        usage=usage_obj,
    )


def _stub_client(responses):
    return SimpleNamespace(chat=SimpleNamespace(
        completions=_StubCompletions(responses)))


def test_provider_accumulates_usage():
    provider = OpenAICompatibleProvider(
        client=_stub_client([_response("a", 10, 5, cache=3),
                             _response("b", 20, 7)]))

    assert provider.chat([{"role": "user", "content": "x"}]) == "a"
    assert provider.chat([{"role": "user", "content": "y"}]) == "b"
    assert provider.calls == 2
    assert provider.prompt_tokens == 30
    assert provider.completion_tokens == 12
    assert provider.cache_hit_tokens == 3  # отсутствующее поле → 0, без падения


def test_usage_handles_missing_cache_field():
    provider = OpenAICompatibleProvider(
        client=_stub_client([_response("x", 10, 5)]))  # без cache-поля

    provider.chat([{"role": "user", "content": "x"}])

    assert provider.cache_hit_tokens == 0


def test_provider_usage_zero_without_usage_payload():
    provider = OpenAICompatibleProvider(
        client=_stub_client([_response("x", 0, 0, usage=False)]))

    provider.chat([{"role": "user", "content": "x"}])

    assert provider.calls == 1
    assert provider.prompt_tokens == 0
    assert provider.completion_tokens == 0


def test_deepseek_client_usage_property():
    client = DeepSeekClient(api_key="test-key")
    client._provider._client = _stub_client([_response('{"ok": true}', 100, 20)])

    raw = client._call([{"role": "user", "content": "x"}], temperature=0.0)

    assert raw == '{"ok": true}'
    assert client.usage == {"calls": 1, "prompt_tokens": 100,
                            "completion_tokens": 20, "cache_hit_tokens": 0}


def test_peak_hour_windows():
    """Peak DeepSeek: 01–04 и 06–10 UTC Пн–Пт; выходные — off-peak."""
    from datetime import datetime, timezone

    from aeon.config import is_peak_hour

    assert is_peak_hour(datetime(2026, 10, 12, 2, 0, tzinfo=timezone.utc)) is True   # Пн
    assert is_peak_hour(datetime(2026, 10, 12, 5, 0, tzinfo=timezone.utc)) is False  # Пн, между окнами
    assert is_peak_hour(datetime(2026, 10, 12, 6, 30, tzinfo=timezone.utc)) is True  # Пн
    assert is_peak_hour(datetime(2026, 10, 17, 2, 0, tzinfo=timezone.utc)) is False  # Сб


def _stub_with_recording(response):
    completions = _StubCompletions([response])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return client, completions


def test_provider_passes_extra_body():
    client, completions = _stub_with_recording(_response("x", 1, 1))
    provider = OpenAICompatibleProvider(client=client)

    provider.chat([{"role": "user", "content": "x"}],
                  extra_body={"thinking": {"type": "disabled"}})

    assert completions.last_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_deepseek_client_disables_thinking_for_flash():
    """2.7.3-fix: flash — thinking-модель; шлём thinking=disabled."""
    client, completions = _stub_with_recording(_response('{"ok": true}', 1, 1))
    deepseek = DeepSeekClient(api_key="k", model="deepseek-flash")
    deepseek._provider._client = client

    deepseek._call([{"role": "user", "content": "x"}], temperature=0.0)

    assert completions.last_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_deepseek_client_no_extra_body_for_chat_alias():
    client, completions = _stub_with_recording(_response('{"ok": true}', 1, 1))
    deepseek = DeepSeekClient(api_key="k", model="deepseek-chat")
    deepseek._provider._client = client

    deepseek._call([{"role": "user", "content": "x"}], temperature=0.0)

    assert "extra_body" not in completions.last_kwargs


def test_provider_retries_on_length():
    """Design principle (3.2/t2): finish_reason=length → retry x2 budget, usage суммируется."""
    completions = _StubCompletions([
        _response('{"partial":', 10, 2000, finish="length"),
        _response('{"full": true}', 12, 50, finish="stop"),
    ])
    provider = OpenAICompatibleProvider(
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))

    result = provider.chat([{"role": "user", "content": "x"}], max_tokens=2000)

    assert result == '{"full": true}'
    assert completions.last_kwargs["max_tokens"] == 4000
    assert provider.calls == 1
    assert provider.prompt_tokens == 22
    assert provider.completion_tokens == 2050


def test_provider_no_retry_on_stop_or_none():
    completions = _StubCompletions([_response("ok", 1, 1, finish="stop")])
    provider = OpenAICompatibleProvider(
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))

    assert provider.chat([{"role": "user", "content": "x"}], max_tokens=2000) == "ok"
    assert completions.last_kwargs["max_tokens"] == 2000
    assert provider.calls == 1


def test_finish_reason_retry_exhausted():
    """length → retry ×2 budget → снова length → возврат partial, без loop; usage суммируется."""
    completions = _StubCompletions([
        _response('{"a":', 10, 2000, finish="length"),
        _response('{"a": 1', 12, 4000, finish="length"),
    ])
    provider = OpenAICompatibleProvider(
        client=SimpleNamespace(chat=SimpleNamespace(completions=completions)))

    result = provider.chat([{"role": "user", "content": "x"}], max_tokens=2000)

    assert result == '{"a": 1'          # последний ответ возвращается как есть
    assert completions.last_kwargs["max_tokens"] == 4000  # один retry, не бесконечность
    assert completions._responses == []  # третьего вызова нет
    assert provider.calls == 1
    assert provider.prompt_tokens == 22
    assert provider.completion_tokens == 6000  # usage обоих вызовов просуммирован
