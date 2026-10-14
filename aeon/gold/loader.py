"""
gold-standard loader (шаг 3.3): JSONL → GoldDataset + integrity-валидация.

Контракт: запись описывается gold/annotation_schema.json (stdlib-валидатор,
без jsonschema). Проверки:
  - обязательные поля и типы; schema_version — semver; annotator — human:<handle>|mock;
  - segment_text — точная УНИКАЛЬНАЯ подстрока texts/<text_id>.txt;
  - offsets маркеров: segment_text[offset:offset+len(text)] == text;
  - сегменты одного текста не перекрываются (offset-матчинг маркеров);
  - mode="ci": annotator="mock" → GoldError (не валидная gold-разметка).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_ANNOTATOR_RE = re.compile(r"^(human:[A-Za-z0-9][A-Za-z0-9_-]*|mock)$")
MARKER_KINDS = frozenset({"lacuna", "supplement", "editorial", "deletion",
                          "uncertain", "crux"})
_ATOM_KEYS = ("intent", "domain", "is_fragment", "completeness_score")
_VERDICT_KEYS = ("detective", "expert", "logician")
_REQUIRED = ("schema_version", "text_id", "language", "segment_id", "segment_text",
             "marker_offsets_relative_to", "annotator", "annotation_date",
             "expected_atom", "expected_markers", "expected_entities",
             "expected_verdicts")


class GoldError(ValueError):
    """Некорректный gold-датасет."""


@dataclass
class GoldRecord:
    text_id: str
    language: str
    segment_id: int
    segment_text: str
    schema_version: str
    annotator: str
    annotation_date: str
    annotator_notes: str = ""
    expected_atom: Dict[str, Any] = field(default_factory=dict)
    expected_markers: List[Dict[str, Any]] = field(default_factory=list)
    expected_entities: List[Dict[str, Any]] = field(default_factory=list)
    expected_verdicts: Optional[Dict[str, str]] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GoldDataset:
    records: List[GoldRecord]
    annotations_dir: str = ""

    def by_text(self) -> Dict[str, List[GoldRecord]]:
        grouped: Dict[str, List[GoldRecord]] = {}
        for record in self.records:
            grouped.setdefault(record.text_id, []).append(record)
        return grouped

    def version(self) -> str:
        versions = {record.schema_version for record in self.records}
        return max(versions) if versions else ""


def _require(record: Dict[str, Any], keys, where: str) -> None:
    missing = [key for key in keys if key not in record]
    if missing:
        raise GoldError(f"{where}: отсутствуют обязательные поля: {missing}")


def _validate_record(record: Dict[str, Any], text_id: str, line_no: int,
                     full_text: str, mode: str) -> GoldRecord:
    where = f"{text_id}.jsonl:{line_no}"
    if not isinstance(record, dict):
        raise GoldError(f"{where}: запись не JSON-объект")
    _require(record, _REQUIRED, where)

    if not _SEMVER_RE.match(str(record["schema_version"])):
        raise GoldError(f"{where}: schema_version '{record['schema_version']}' не semver")
    if record["text_id"] != text_id:
        raise GoldError(f"{where}: text_id '{record['text_id']}' ≠ имени файла")
    annotator = str(record["annotator"])
    if not _ANNOTATOR_RE.match(annotator):
        raise GoldError(f"{where}: annotator '{annotator}' (ожидается human:<handle>|mock)")
    if mode == "ci" and annotator == "mock":
        raise GoldError(f"{where}: annotator=mock не является валидной gold-разметкой (mode=ci)")
    if record["marker_offsets_relative_to"] != "segment":
        raise GoldError(f"{where}: marker_offsets_relative_to должен быть 'segment'")

    segment = str(record["segment_text"])
    if segment not in full_text:
        raise GoldError(f"{where}: segment_text не найдена в texts/{text_id}.txt")
    if full_text.count(segment) != 1:
        raise GoldError(f"{where}: segment_text не уникальна в тексте")

    atom = record["expected_atom"]
    _require(atom, _ATOM_KEYS, f"{where}.expected_atom")
    if not (0.0 <= float(atom["completeness_score"]) <= 1.0):
        raise GoldError(f"{where}.expected_atom.completeness_score вне [0,1]")

    for index, marker in enumerate(record["expected_markers"]):
        mwhere = f"{where}.expected_markers[{index}]"
        _require(marker, ("kind", "text", "offset"), mwhere)
        if marker["kind"] not in MARKER_KINDS:
            raise GoldError(f"{mwhere}: kind '{marker['kind']}' вне таксономии")
        offset = int(marker["offset"])
        marker_text = str(marker["text"])
        if segment[offset:offset + len(marker_text)] != marker_text:
            raise GoldError(
                f"{mwhere}: offset {offset} не указывает на {marker_text!r} "
                f"(найдено {segment[offset:offset + len(marker_text)]!r})"
            )

    for index, entity in enumerate(record["expected_entities"]):
        ewhere = f"{where}.expected_entities[{index}]"
        _require(entity, ("name", "wikidata_id", "is_fragment"), ewhere)
        qid = entity["wikidata_id"]
        if qid is not None and not re.match(r"^Q[0-9]+$", str(qid)):
            raise GoldError(f"{ewhere}: wikidata_id '{qid}' не Q-ID и не null")

    verdicts = record["expected_verdicts"]
    if verdicts is not None:
        _require(verdicts, _VERDICT_KEYS, f"{where}.expected_verdicts")

    return GoldRecord(
        text_id=text_id,
        language=str(record["language"]),
        segment_id=int(record["segment_id"]),
        segment_text=segment,
        schema_version=str(record["schema_version"]),
        annotator=annotator,
        annotation_date=str(record["annotation_date"]),
        annotator_notes=str(record.get("annotator_notes") or ""),
        expected_atom=dict(atom),
        expected_markers=[dict(marker) for marker in record["expected_markers"]],
        expected_entities=[dict(entity) for entity in record["expected_entities"]],
        expected_verdicts=dict(verdicts) if verdicts is not None else None,
        raw=record,
    )


def load_dataset(annotations_dir, *, texts_dir=None, mode: str = "ci") -> GoldDataset:
    """Загрузка и валидация датасета. mode: "ci" | "research"."""
    path = Path(annotations_dir)
    files = sorted(path.glob("*.jsonl"))
    if not files:
        raise GoldError(f"пустой датасет: {path} не содержит *.jsonl")
    texts_path = Path(texts_dir) if texts_dir else path.parent / "texts"

    records: List[GoldRecord] = []
    for file in files:
        text_id = file.stem
        text_file = texts_path / f"{text_id}.txt"
        if not text_file.exists():
            raise GoldError(f"{text_id}: нет texts/{text_id}.txt")
        full_text = text_file.read_text(encoding="utf-8").strip()
        for line_no, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GoldError(f"{text_id}.jsonl:{line_no}: JSON-ошибка: {exc}") from exc
            records.append(_validate_record(record, text_id, line_no, full_text, mode))

    dataset = GoldDataset(records, str(path))
    _check_non_overlap(dataset, texts_path)
    return dataset


def _check_non_overlap(dataset: GoldDataset, texts_path: Path) -> None:
    """Сегменты одного текста не перекрываются (иначе сломается offset-матчинг)."""
    for text_id, records in dataset.by_text().items():
        full_text = (texts_path / f"{text_id}.txt").read_text(encoding="utf-8").strip()
        spans = []
        for record in records:
            start = full_text.find(record.segment_text)
            spans.append((start, start + len(record.segment_text)))
        spans.sort()
        for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
            if s2 < e1:
                raise GoldError(f"{text_id}: сегменты перекрываются: {(s1, e1)} vs {(s2, e2)}")
