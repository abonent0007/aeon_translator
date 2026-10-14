"""Тесты JSON-lines логирования (aeon/logging_config.py)."""

import json

from aeon.logging_config import get_logger, log_event


def _read_lines(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_json_lines_format(tmp_path):
    logger = get_logger("aeon.test.format", log_file=tmp_path / "log.jsonl")
    log_event(
        logger,
        "verdict",
        agent="detective",
        verdict="grounded",
        confidence=0.87,
        sources=["Q859"],
        reasoning="exact quote found",
        trace_id="run-1",
    )

    lines = _read_lines(tmp_path / "log.jsonl")
    assert len(lines) == 1
    event = lines[0]
    assert event["level"] == "INFO"
    assert event["logger"] == "aeon.test.format"
    assert event["msg"] == "verdict"
    assert event["agent"] == "detective"
    assert event["verdict"] == "grounded"
    assert event["confidence"] == 0.87
    assert event["sources"] == ["Q859"]
    assert event["reasoning"] == "exact quote found"
    assert event["trace_id"] == "run-1"
    assert event["ts"].endswith("Z")


def test_every_line_is_valid_json(tmp_path):
    logger = get_logger("aeon.test.multi", log_file=tmp_path / "multi.jsonl")
    log_event(logger, "start")
    log_event(logger, "check", agent="expert", confidence=0.5)
    log_event(logger, "done", verdict="verified")

    lines = _read_lines(tmp_path / "multi.jsonl")
    assert [e["msg"] for e in lines] == ["start", "check", "done"]
    assert lines[1]["agent"] == "expert"


def test_extra_fields_pass_through(tmp_path):
    logger = get_logger("aeon.test.extra", log_file=tmp_path / "extra.jsonl")
    log_event(logger, "link", entity="Александр Македонский", qid="Q8409", rank=1)

    event = _read_lines(tmp_path / "extra.jsonl")[0]
    assert event["entity"] == "Александр Македонский"
    assert event["qid"] == "Q8409"
    assert event["rank"] == 1


def test_same_logger_not_reconfigured(tmp_path):
    logger = get_logger("aeon.test.same", log_file=tmp_path / "first.jsonl")
    again = get_logger("aeon.test.same", log_file=tmp_path / "second.jsonl")
    assert again is logger
    assert len(logger.handlers) == 1
