"""
gold-runner (шаг 3.3): прогон AEON pipeline на gold-текстах.

mock-режим: MockLLM с canned-ответами из gold/fixtures/mock_responses.json —
СОЗНАТЕЛЬНО не совпадающими с gold-аннотациями (анти-циркулярность, стоп №2).
real-режим: DeepSeekClient (нужен ключ; вне CI).

Resilience (2.7.3): исключение на одном сегменте НЕ роняет прогон —
сегмент помечается failed (пустой prediction), пишется событие
`gold_text_failed`, прогон продолжается; failures собираются в stats.

Markers/is_fragment оцениваются паком языка детерминированно (без LLM);
entities/completeness — extractor; verdicts — Verification 2.0 (только если
gold-запись содержит expected_verdicts).
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logging_config import get_logger, log_event
from .loader import GoldDataset, GoldError

_LOGGER = get_logger("aeon.gold")

_FIXTURE = (Path(__file__).resolve().parent.parent.parent
            / "gold" / "fixtures" / "mock_responses.json")


@dataclass
class GoldPrediction:
    text_id: str
    segment_id: int
    markers: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    is_fragment: bool = False
    completeness: float = 1.0
    verdicts: Optional[Dict[str, str]] = None
    failed: bool = False
    error: str = ""


def _make_llm(mode: str, latency_ms: float):
    if mode == "real":
        from ..llm_client import DeepSeekClient

        llm = DeepSeekClient()
        if not llm.available:
            raise GoldError("real-режим требует DEEPSEEK_API_KEY (в .env или окружении)")
        return llm
    from ..testing import MockLLM

    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return MockLLM(responses=fixture["responses"], latency_ms=latency_ms)


def _offline_embeddings():
    from ..embeddings import EmbeddingEngine

    engine = EmbeddingEngine()
    engine.available = False
    return engine


def _snapshot_usage(llm: Any) -> tuple:
    """(calls, prompt_tokens, completion_tokens, cache_hit_tokens)."""
    usage = dict(getattr(llm, "usage", {}) or {})
    if usage:
        return (int(usage.get("calls", 0)),
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                int(usage.get("cache_hit_tokens", 0)))
    return (len(getattr(llm, "calls", None) or []), 0, 0, 0)


def attach_raw_recorder(llm: Any, raw_dir) -> Path:
    """Патч `llm._call`: каждый сырой ответ → <raw_dir>/llm_calls.jsonl (аудит).

    Работает и для MockLLM, и для DeepSeekClient: перехватывает нижний уровень
    `_call` (через который идёт и `_call_json`), поэтому записываются ВСЕ вызовы.
    """
    directory = Path(raw_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "llm_calls.jsonl"
    original = llm._call

    def recording(messages, *args, **kwargs):
        raw = original(messages, *args, **kwargs)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"messages": messages, "raw": raw},
                                    ensure_ascii=False) + "\n")
        return raw

    llm._call = recording
    return path


def _predict_record(record, llm: Any, packs: Dict[str, Any],
                    with_verdicts: bool) -> GoldPrediction:
    """Один сегмент: markers (pack) + extract (LLM) + verdicts (LLM, опц.)."""
    from ..extractor import MeaningExtractor
    from ..language import get as get_pack
    from ..verification import VerificationEngine, build_claims

    pack = packs.setdefault(record.language, get_pack(record.language))
    segment = record.segment_text

    markers = [{"kind": marker.kind, "text": marker.text, "offset": marker.start}
               for marker in pack.detect_markers(segment)]

    extractor = MeaningExtractor(llm_client=llm, embedding_engine=_offline_embeddings())
    atom = extractor.extract_from_text(segment, record.language)
    entities = [{"name": entity.name, "wikidata_id": None}
                for entity in atom.entities]

    verdicts = None
    if with_verdicts and record.expected_verdicts is not None:
        verification = VerificationEngine(llm_client=llm)
        verification.embeddings = _offline_embeddings()
        claims = build_claims(atom, trace_id=f"gold:{record.text_id}:{record.segment_id}")
        result = verification.verify_atom(
            segment, claims, [entity["name"] for entity in entities],
            trace_id=f"gold:{record.text_id}:{record.segment_id}", mode="full")
        verdicts = {name: payload["verdict"]
                    for name, payload in result["agents"].items()}

    return GoldPrediction(
        text_id=record.text_id,
        segment_id=record.segment_id,
        markers=markers,
        entities=entities,
        is_fragment=bool(pack.is_fragment(segment)),
        completeness=float(atom.completeness_score),
        verdicts=verdicts,
    )


def run_dataset(dataset: GoldDataset, *, mode: str = "mock",
                latency_ms: float = 0.0, with_verdicts: bool = True,
                llm: Any = None, raw_dir: Optional[str] = None,
                stats: Optional[Dict[str, Any]] = None
                ) -> Dict[str, List[GoldPrediction]]:
    """Прогон по всем записям датасета → {text_id: [GoldPrediction, ...]}.

    raw_dir — сохранять сырые LLM-ответы (аудит real-прогонов);
    stats — заполняется in-place: calls/prompt_tokens/completion_tokens/
    latency_sec (итого) + per_text + failures (resilient per-segment).
    """
    llm = llm if llm is not None else _make_llm(mode, latency_ms)
    if raw_dir:
        attach_raw_recorder(llm, raw_dir)
    usage_before = _snapshot_usage(llm)
    started = time.perf_counter()

    predictions: Dict[str, List[GoldPrediction]] = {}
    packs: Dict[str, Any] = {}
    failures: List[Dict[str, Any]] = []

    for record in dataset.records:
        before = _snapshot_usage(llm)
        segment_started = time.perf_counter()
        try:
            prediction = _predict_record(record, llm, packs, with_verdicts)
        except Exception as exc:  # resilience (2.7.3): не роняем прогон
            log_event(_LOGGER, "gold_text_failed",
                      text_id=record.text_id, segment_id=record.segment_id,
                      error=str(exc)[:200],
                      trace_id=f"gold:{record.text_id}:{record.segment_id}")
            prediction = GoldPrediction(
                text_id=record.text_id, segment_id=record.segment_id,
                is_fragment=False, completeness=0.0,
                failed=True, error=str(exc)[:200])
            failures.append({"text_id": record.text_id,
                             "segment_id": record.segment_id,
                             "error": str(exc)[:200]})
        predictions.setdefault(record.text_id, []).append(prediction)

        if stats is not None:
            after = _snapshot_usage(llm)
            waited = time.perf_counter() - segment_started
            entry = stats.setdefault("per_text", {}).setdefault(
                record.text_id, {"calls": 0, "prompt_tokens": 0,
                                 "completion_tokens": 0, "cache_hit_tokens": 0,
                                 "latency_sec": 0.0})
            entry["calls"] += after[0] - before[0]
            entry["prompt_tokens"] += after[1] - before[1]
            entry["completion_tokens"] += after[2] - before[2]
            entry["cache_hit_tokens"] += after[3] - before[3]
            entry["latency_sec"] = round(entry["latency_sec"] + waited, 2)

    if stats is not None:
        from ..config import is_peak_hour

        usage_after = _snapshot_usage(llm)
        stats["latency_sec"] = round(time.perf_counter() - started, 2)
        stats["mode"] = mode
        stats["calls"] = usage_after[0] - usage_before[0]
        stats["prompt_tokens"] = usage_after[1] - usage_before[1]
        stats["completion_tokens"] = usage_after[2] - usage_before[2]
        stats["cache_hit_tokens"] = usage_after[3] - usage_before[3]
        stats["peak_hour"] = is_peak_hour()
        stats["failures"] = failures
    return predictions
