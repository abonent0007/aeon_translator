"""
gold-runner (шаг 3.3): прогон AEON pipeline на gold-текстах.

mock-режим: MockLLM с canned-ответами из gold/fixtures/mock_responses.json —
СОЗНАТЕЛЬНО не совпадающими с gold-аннотациями (анти-циркулярность, стоп №2).
real-режим: DeepSeekClient (нужен ключ; вне CI).

Markers/is_fragment оцениваются паком языка детерминированно (без LLM);
entities/completeness — extractor; verdicts — Verification 2.0 (только если
gold-запись содержит expected_verdicts).
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .loader import GoldDataset, GoldError

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


def run_dataset(dataset: GoldDataset, *, mode: str = "mock",
                latency_ms: float = 0.0, with_verdicts: bool = True,
                llm: Any = None, raw_dir: Optional[str] = None,
                stats: Optional[Dict[str, Any]] = None
                ) -> Dict[str, List[GoldPrediction]]:
    """Прогон по всем записям датасета → {text_id: [GoldPrediction, ...]}.

    raw_dir — сохранять сырые LLM-ответы (аудит real-прогонов);
    stats — заполняется in-place: calls/prompt_tokens/completion_tokens/latency_sec.
    """
    from ..extractor import MeaningExtractor
    from ..language import get as get_pack
    from ..verification import VerificationEngine

    llm = llm if llm is not None else _make_llm(mode, latency_ms)
    if raw_dir:
        attach_raw_recorder(llm, raw_dir)
    usage_before = dict(getattr(llm, "usage", {}) or {})
    mock_calls_before = len(getattr(llm, "calls", None) or [])
    started = time.perf_counter()

    predictions: Dict[str, List[GoldPrediction]] = {}
    packs: Dict[str, Any] = {}

    for record in dataset.records:
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
            claims = (atom.explanation_chain or []) + [
                f"Intent: {atom.intent}", f"Domain: {atom.domain}"]
            result = verification.verify_atom(
                segment, claims, [entity["name"] for entity in entities],
                trace_id=f"gold:{record.text_id}:{record.segment_id}", mode="full")
            verdicts = {name: payload["verdict"]
                        for name, payload in result["agents"].items()}

        predictions.setdefault(record.text_id, []).append(GoldPrediction(
            text_id=record.text_id,
            segment_id=record.segment_id,
            markers=markers,
            entities=entities,
            is_fragment=bool(pack.is_fragment(segment)),
            completeness=float(atom.completeness_score),
            verdicts=verdicts,
        ))

    if stats is not None:
        usage_after = dict(getattr(llm, "usage", {}) or {})
        stats["latency_sec"] = round(time.perf_counter() - started, 2)
        stats["mode"] = mode
        if usage_after:
            stats["calls"] = int(usage_after.get("calls", 0)
                                 - usage_before.get("calls", 0))
            stats["prompt_tokens"] = int(usage_after.get("prompt_tokens", 0)
                                         - usage_before.get("prompt_tokens", 0))
            stats["completion_tokens"] = int(
                usage_after.get("completion_tokens", 0)
                - usage_before.get("completion_tokens", 0))
        else:  # MockLLM: считаем по списку вызовов, токены не имитируем
            stats["calls"] = len(getattr(llm, "calls", None) or []) - mock_calls_before
            stats["prompt_tokens"] = 0
            stats["completion_tokens"] = 0
    return predictions
