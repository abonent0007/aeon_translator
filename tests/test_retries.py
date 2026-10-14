"""Тесты ретраев LLM-вызовов (aeon/llm/retries.py)."""

import pytest

from aeon.llm.retries import is_retryable, retry_call


class Boom(Exception):
    def __init__(self, status_code=None):
        super().__init__(f"boom {status_code}")
        if status_code is not None:
            self.status_code = status_code


def test_success_first_attempt():
    result, attempts, delays = retry_call(lambda: 42)
    assert result == 42
    assert attempts == 1
    assert delays == []


def test_retry_then_success_with_backoff():
    calls = {"n": 0}
    slept = []

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Boom(500)
        return "ok"

    result, attempts, delays = retry_call(fn, sleep=slept.append, base_delay=0.5)
    assert result == "ok"
    assert attempts == 3
    assert delays == [0.5, 1.0]
    assert slept == [0.5, 1.0]


def test_non_retryable_fails_fast():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise Boom(400)

    with pytest.raises(Boom):
        retry_call(fn, sleep=lambda _: None)
    assert calls["n"] == 1


def test_max_attempts_exhausted():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise Boom(503)

    with pytest.raises(Boom):
        retry_call(fn, max_attempts=3, sleep=lambda _: None)
    assert calls["n"] == 3


def test_on_retry_callback_fires():
    events = []

    def fn():
        if not events:
            raise Boom(429)
        return "ok"

    retry_call(
        fn,
        on_retry=lambda attempt, delay, exc: events.append((attempt, delay)),
        sleep=lambda _: None,
    )
    assert events == [(1, 0.5)]


def test_is_retryable_classification():
    assert is_retryable(Boom(500))
    assert is_retryable(Boom(503))
    assert is_retryable(Boom(429))
    assert is_retryable(Boom(408))
    assert not is_retryable(Boom(400))
    assert not is_retryable(Boom(401))
    assert not is_retryable(Boom(404))
    assert not is_retryable(Boom())  # без статуса — не ретраим


class BoomWithHeaders(Exception):
    def __init__(self, status_code, retry_after=None):
        super().__init__(f"http {status_code}")
        self.status_code = status_code
        if retry_after is not None:
            self.response = type(
                "R", (), {"headers": {"retry-after": str(retry_after)}}
            )()


def test_retry_after_hint_overrides_backoff():
    slept = []
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise BoomWithHeaders(429, retry_after=2)
        return "ok"

    result, attempts, delays = retry_call(fn, base_delay=0.5, sleep=slept.append)

    assert result == "ok"
    assert slept == [2.0]  # max(backoff 0.5, Retry-After 2)
    assert delays == [2.0]


def test_retry_after_smaller_than_backoff():
    slept = []
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise BoomWithHeaders(429, retry_after=0.1)
        return "ok"

    _, _, delays = retry_call(fn, base_delay=0.5, sleep=slept.append)

    assert slept == [0.5]  # backoff больше Retry-After
    assert delays == [0.5]
