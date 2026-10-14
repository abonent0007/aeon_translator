"""
AEON Variant Readings — apparatus criticus (шаг 3.5).

Философия (preflight): LLM только ВЫБИРАЕТ между внешне заданными
attested readings; генерация запрещена. Attribution ОБЯЗАТЕЛЕН —
reading без editions или с неизвестным изданием → ApparatusError.
Формат — sidecar-JSON (схема schemas/apparatus_v1.json), stdlib-валидатор.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_WORK_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)  # без '_' — имена файлов/стемы


class ApparatusError(ValueError):
    """Некорректный apparatus (attribution, версия, структура)."""


@dataclass
class Reading:
    text: str
    editions: List[str] = field(default_factory=list)  # ≥1, иначе ApparatusError


@dataclass
class Locus:
    line: Union[int, str]
    context: str = ""
    readings: List[Reading] = field(default_factory=list)  # ≥2 (contest)


@dataclass
class Apparatus:
    work: str
    editions: List[str]
    loci: List[Locus]
    apparatus_version: str


def load_apparatus(path) -> Apparatus:
    """Парсинг и валидация sidecar-JSON (stdlib)."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ApparatusError("apparatus должен быть JSON-объектом")

    work = str(payload.get("work") or "").strip()
    if not work:
        raise ApparatusError("apparatus.work обязателен")

    version = str(payload.get("apparatus_version") or "").strip()
    if not _SEMVER_RE.match(version):
        raise ApparatusError(f"apparatus_version '{version}' не semver (X.Y.Z)")

    editions = payload.get("editions") or []
    if not isinstance(editions, list) or not editions:
        raise ApparatusError("apparatus.editions: непустой список обязателен")
    editions = [str(e) for e in editions]
    editions_set = set(editions)

    loci_payload = payload.get("loci") or []
    if not isinstance(loci_payload, list) or not loci_payload:
        raise ApparatusError("apparatus.loci: непустой список обязателен")

    loci: List[Locus] = []
    for index, item in enumerate(loci_payload):
        if not isinstance(item, dict) or "line" not in item:
            raise ApparatusError(f"locus[{index}]: поле 'line' обязательно")
        raw_readings = item.get("readings") or []
        if len(raw_readings) < 2:
            raise ApparatusError(
                f"locus[{index}] (line={item['line']}): минимум 2 readings "
                f"(одиночное чтение — не contest)"
            )
        readings: List[Reading] = []
        for r_index, raw_reading in enumerate(raw_readings):
            text = str((raw_reading or {}).get("text") or "").strip()
            if not text:
                raise ApparatusError(f"locus[{index}].readings[{r_index}]: пустой text")
            reading_editions = (raw_reading or {}).get("editions") or []
            if not reading_editions:
                raise ApparatusError(
                    f"locus[{index}].readings[{r_index}]: ATTRIBUTION ОБЯЗАТЕЛЕН — "
                    f"reading без editions запрещён"
                )
            for edition in reading_editions:
                if str(edition) not in editions_set:
                    raise ApparatusError(
                        f"locus[{index}].readings[{r_index}]: неизвестное издание "
                        f"'{edition}' (нет в apparatus.editions)"
                    )
            readings.append(Reading(text=text,
                                    editions=[str(e) for e in reading_editions]))
        loci.append(Locus(line=item["line"], context=str(item.get("context") or ""),
                          readings=readings))

    return Apparatus(work=work, editions=editions, loci=loci,
                     apparatus_version=version)


def work_tokens(work: str) -> set:
    """Значимые токены названия работы (≥4 симв., casefold)."""
    return {token.casefold() for token in _WORK_TOKEN_RE.findall(work or "")
            if len(token) > 3}
