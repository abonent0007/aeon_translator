"""
gold-метрики (шаг 3.3) — stdlib only (statistics), без pandas/numpy/HF.

Метрики:
  - markers: P/R/F1 per kind (матч: тот же kind + пересечение отрезков
    [offset, offset+len(text))); macro — среднее F1 по kind'ам;
  - entities: P/R/F1 (матч: exact Q-ID, если ОБА не-null; иначе casefold-равенство
    имени);
  - is_fragment: accuracy (бинарная);
  - completeness_score: MAE (mean absolute error);
  - verdicts: accuracy per агент (только записи с заполненным expected).
"""

from typing import Any, Dict, List, Tuple, Union

import unicodedata

from .loader import GoldDataset, GoldRecord


def _fold(text: Any) -> str:
    """Коммит 4 (2.7.3): NFKD + снятие комбинируемых знаков + casefold.

    Матчинг имён без Q-ID не должен зависеть от варианта диакритики
    (grave/acute: Διός vs Διὸς, Ἀκαμαντίς vs Ἀκαμαντὶς) — только для
    СРАВНЕНИЯ, не для вывода/хранения.
    """
    base = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(ch for ch in base if not unicodedata.combining(ch))
    return stripped.casefold()


def _prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def _overlap(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    a_start, a_end = a["offset"], a["offset"] + len(str(a["text"]))
    b_start, b_end = b["offset"], b["offset"] + len(str(b["text"]))
    return a_start < b_end and b_start < a_end


def markers_prf(expected: List[Dict], predicted: List[Dict]) -> Dict[str, Any]:
    """P/R/F1 per kind + macro (среднее F1 по kind'ам с непустым конкурентом)."""
    kinds = sorted({m["kind"] for m in expected} | {m["kind"] for m in predicted})
    per_kind: Dict[str, Dict[str, float]] = {}
    for kind in kinds:
        exp = [m for m in expected if m["kind"] == kind]
        pred = [m for m in predicted if m["kind"] == kind]
        used = set()
        tp = 0
        for marker in exp:
            for index, candidate in enumerate(pred):
                if index in used:
                    continue
                if _overlap(marker, candidate):
                    tp += 1
                    used.add(index)
                    break
        per_kind[kind] = _prf(tp, len(pred) - tp, len(exp) - tp)
    f1_values = [per_kind[kind]["f1"] for kind in kinds
                 if per_kind[kind]["tp"] + per_kind[kind]["fp"] + per_kind[kind]["fn"] > 0]
    macro = round(sum(f1_values) / len(f1_values), 4) if f1_values else 1.0
    return {"per_kind": per_kind, "macro_f1": macro}


def entities_prf(expected: List[Dict], predicted: List[Dict]) -> Dict[str, float]:
    """Матч: exact Q-ID, если оба не-null; иначе accent-insensitive имя (коммит 4)."""
    used = set()
    tp = 0
    for entity in expected:
        for index, candidate in enumerate(predicted):
            if index in used:
                continue
            exp_qid, pred_qid = entity.get("wikidata_id"), candidate.get("wikidata_id")
            if exp_qid and pred_qid:
                matched = str(exp_qid) == str(pred_qid)
            else:
                matched = _fold(entity.get("name", "")) == _fold(candidate.get("name", ""))
            if matched:
                tp += 1
                used.add(index)
                break
    return _prf(tp, len(predicted) - tp, len(expected) - tp)


def is_fragment_accuracy(pairs: List[Tuple[bool, bool]]) -> float:
    if not pairs:
        return 1.0
    return round(sum(1 for expected, predicted in pairs if expected == predicted)
                 / len(pairs), 4)


def completeness_mae(pairs: List[Tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    return round(sum(abs(float(expected) - float(predicted))
                     for expected, predicted in pairs) / len(pairs), 4)


def verdict_accuracy(triples: List[Tuple[Dict[str, str], Dict[str, str]]]) -> Dict[str, float]:
    """Accuracy per агент (только записи с заполненным expected)."""
    if not triples:
        return {}
    result: Dict[str, float] = {}
    for agent in ("detective", "expert", "logician"):
        pairs = [(expected.get(agent), predicted.get(agent)) for expected, predicted in triples]
        pairs = [(e, p) for e, p in pairs if e is not None]
        if pairs:
            result[agent] = round(sum(1 for e, p in pairs if e == p) / len(pairs), 4)
    return result


def evaluate_dataset(dataset: GoldDataset, predictions: Dict[str, List[Any]]) -> Dict[str, Any]:
    """Метрики per text + aggregate. predictions: {text_id: [GoldPrediction, ...]}."""
    per_text: Dict[str, Any] = {}
    all_marker_tp: Dict[str, Dict[str, float]] = {}
    entity_totals = {"tp": 0, "fp": 0, "fn": 0}
    fragment_pairs: List[Tuple[bool, bool]] = []
    completeness_pairs: List[Tuple[float, float]] = []
    verdict_triples: List[Tuple[Dict, Dict]] = []

    for text_id, records in dataset.by_text().items():
        predicted_list = predictions.get(text_id, [])
        expected_markers: List[Dict] = []
        predicted_markers: List[Dict] = []
        expected_entities: List[Dict] = []
        predicted_entities: List[Dict] = []
        text_fragment_pairs: List[Tuple[bool, bool]] = []
        text_completeness_pairs: List[Tuple[float, float]] = []
        text_verdict_triples: List[Tuple[Dict, Dict]] = []

        for record, prediction in zip(records, predicted_list):
            expected_markers.extend(record.expected_markers)
            predicted_markers.extend(prediction.markers)
            expected_entities.extend(record.expected_entities)
            predicted_entities.extend(prediction.entities)
            text_fragment_pairs.append(
                (bool(record.expected_atom["is_fragment"]), bool(prediction.is_fragment)))
            text_completeness_pairs.append(
                (float(record.expected_atom["completeness_score"]),
                 float(prediction.completeness)))
            if record.expected_verdicts and prediction.verdicts:
                text_verdict_triples.append((record.expected_verdicts, prediction.verdicts))

        marker_metrics = markers_prf(expected_markers, predicted_markers)
        entity_metrics = entities_prf(expected_entities, predicted_entities)
        per_text[text_id] = {
            "segments": len(records),
            "markers": marker_metrics,
            "entities": entity_metrics,
            "is_fragment_accuracy": is_fragment_accuracy(text_fragment_pairs),
            "completeness_mae": completeness_mae(text_completeness_pairs),
            "verdicts": verdict_accuracy(text_verdict_triples),
        }
        for kind, counts in marker_metrics["per_kind"].items():
            bucket = all_marker_tp.setdefault(kind, {"tp": 0, "fp": 0, "fn": 0})
            bucket["tp"] += counts["tp"]
            bucket["fp"] += counts["fp"]
            bucket["fn"] += counts["fn"]
        entity_totals["tp"] += entity_metrics["tp"]
        entity_totals["fp"] += entity_metrics["fp"]
        entity_totals["fn"] += entity_metrics["fn"]
        fragment_pairs.extend(text_fragment_pairs)
        completeness_pairs.extend(text_completeness_pairs)
        verdict_triples.extend(text_verdict_triples)

    aggregate_markers = {kind: _prf(**counts) for kind, counts in all_marker_tp.items()}
    f1_values = [metrics["f1"] for metrics in aggregate_markers.values()
                 if metrics["tp"] + metrics["fp"] + metrics["fn"] > 0]
    aggregate = {
        "segments": len(dataset.records),
        "markers": {"per_kind": aggregate_markers,
                    "macro_f1": round(sum(f1_values) / len(f1_values), 4) if f1_values else 1.0},
        "entities": _prf(entity_totals["tp"], entity_totals["fp"], entity_totals["fn"]),
        "is_fragment_accuracy": is_fragment_accuracy(fragment_pairs),
        "completeness_mae": completeness_mae(completeness_pairs),
        "verdicts": verdict_accuracy(verdict_triples),
    }
    return {"per_text": per_text, "aggregate": aggregate}
