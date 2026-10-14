"""Тесты тестового дублёра MockLLM (tests/conftest.py)."""


def test_mock_llm_returns_configured_json(mock_llm):
    mock_llm.responses = {"intent": {"intent": "question"}}

    result = mock_llm._call_json([{"role": "user", "content": "detect intent please"}])
    assert result == {"intent": "question"}


def test_mock_llm_default_response(mock_llm):
    assert mock_llm._call_json([{"role": "user", "content": "unknown"}]) == {}


def test_mock_llm_offline_mode(mock_llm):
    mock_llm.available = False
    assert mock_llm._call([{"role": "user", "content": "hey"}]) == ""
    assert mock_llm._call_json([{"role": "user", "content": "hey"}]) == {}


def test_mock_llm_records_calls(mock_llm):
    mock_llm._call([{"role": "user", "content": "one"}], temperature=0.1)

    assert len(mock_llm.calls) == 1
    assert mock_llm.calls[0]["temperature"] == 0.1


def test_mock_llm_parse_error_channel(mock_llm):
    mock_llm.default = "I cannot answer that."
    data = mock_llm._call_json([{"role": "user", "content": "x"}])
    assert data["parse_error"] == "unrepairable JSON"
