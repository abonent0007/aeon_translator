"""Тесты извлечения/починки JSON из ответов LLM (aeon/llm/json_repair.py)."""

from aeon.llm.json_repair import extract_json


def test_clean_json_passes():
    data, reason = extract_json('{"intent": "question", "complexity": 0.5}')
    assert reason is None
    assert data == {"intent": "question", "complexity": 0.5}


def test_markdown_fence_with_language():
    data, reason = extract_json('```json\n{"a": 1}\n```')
    assert reason is None
    assert data == {"a": 1}


def test_markdown_fence_without_language():
    data, reason = extract_json('```\n{"a": 1}\n```')
    assert reason is None
    assert data == {"a": 1}


def test_unclosed_fence():
    data, reason = extract_json('```json\n{"a": 1}')
    assert reason is None
    assert data == {"a": 1}


def test_text_around_json():
    data, reason = extract_json('Here is the analysis: {"intent": "statement"} Hope it helps!')
    assert reason is None
    assert data == {"intent": "statement"}


def test_trailing_comma():
    data, reason = extract_json('{"a": 1, "b": [1, 2,],}')
    assert reason is None
    assert data == {"a": 1, "b": [1, 2]}


def test_single_quotes_python_literals():
    data, reason = extract_json("{'a': 'b', 'flag': True}")
    assert reason is None
    assert data == {"a": "b", "flag": True}


def test_empty_response():
    data, reason = extract_json("")
    assert data == {}
    assert reason == "empty response"


def test_garbage_unrepairable():
    data, reason = extract_json("I cannot analyze this text.")
    assert data == {}
    assert reason == "unrepairable JSON"


def test_non_object_json_rejected():
    data, reason = extract_json("[1, 2, 3]")
    assert data == {}
    assert reason is not None
