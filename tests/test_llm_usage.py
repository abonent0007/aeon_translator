"""Token/cost tracking (2.7.7) — stub-клиент, 0 сети."""

from types import SimpleNamespace

from aeon.llm.openai_compatible import OpenAICompatibleProvider
from aeon.llm_client import DeepSeekClient


class _StubCompletions:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        return self._responses.pop(0)


def _response(content, prompt_tokens, completion_tokens, usage=True):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=(SimpleNamespace(prompt_tokens=prompt_tokens,
                               completion_tokens=completion_tokens)
               if usage else None),
    )


def _stub_client(responses):
    return SimpleNamespace(chat=SimpleNamespace(
        completions=_StubCompletions(responses)))


def test_provider_accumulates_usage():
    provider = OpenAICompatibleProvider(
        client=_stub_client([_response("a", 10, 5), _response("b", 20, 7)]))

    assert provider.chat([{"role": "user", "content": "x"}]) == "a"
    assert provider.chat([{"role": "user", "content": "y"}]) == "b"
    assert provider.calls == 2
    assert provider.prompt_tokens == 30
    assert provider.completion_tokens == 12


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
                            "completion_tokens": 20}
