"""CLI crossrefs engine (шаг 3.4.2).

Примеры:
  python -m aeon.crossrefs.demo --a gold/texts/homer_iliad_1.txt --b gold/texts/vergil_aen_1.txt --real
  python -m aeon.crossrefs.demo --a gold/texts/catullus_51.txt --b gold/texts/livius_odusia_1.txt --real
  python -m aeon.crossrefs.demo --all-pairs gold/texts --real --json-out gold/real_runs/<run>/predictions.json

Pilot-упрощение: файл = один сегмент (segment 1) — все gold-xref корпуса
ссылаются на seg1; сегментная карта атомов — будущий шаг.
"""

import argparse
import contextlib
import json
import sys
import time
from itertools import combinations
from pathlib import Path

from ..testing import MockLLM
from .engine import CrossReferenceEngine
from .prompts import PROMPT_VERSION

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _detect_lang(text: str) -> str:
    try:
        from ..language import registry

        pack = registry.detect(text)
        return pack.iso_code if pack is not None else "und"
    except Exception:
        return "und"


def _make_llm(real: bool):
    if real:
        from ..llm_client import DeepSeekClient

        llm = DeepSeekClient()
        if not llm.available:
            raise SystemExit("--real требует DEEPSEEK_API_KEY (в .env или окружении)")
        return llm
    return MockLLM(responses={}, default='{"cross_references": []}')


def _usage(llm) -> dict:
    usage = dict(getattr(llm, "usage", {}) or {})
    if usage:
        return usage
    return {"calls": len(getattr(llm, "calls", None) or [])}


def _load_pair(path: Path, text_id: str, lang: str, author: str = "") -> dict:
    text = path.read_text(encoding="utf-8").strip()
    pair = {"text_id": text_id, "lang": lang or _detect_lang(text),
            "segments": [text]}
    if author:
        pair["author_id"] = author
    return pair


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aeon.crossrefs.demo")
    parser.add_argument("--a", help="файл TEXT_A (ранний/источник)")
    parser.add_argument("--b", help="файл TEXT_B (поздний/цель)")
    parser.add_argument("--all-pairs", metavar="DIR",
                        help="все пары *.txt в директории (C(n,2))")
    parser.add_argument("--id-a")
    parser.add_argument("--id-b")
    parser.add_argument("--lang-a", default="")
    parser.add_argument("--lang-b", default="")
    parser.add_argument("--real", action="store_true",
                        help="DeepSeek API (иначе mock)")
    parser.add_argument("--json-out", help="записать результаты в JSON")
    parser.add_argument("--force", action="store_true",
                        help="разрешить перезапись --json-out (защита от "
                             "двойного прогона, design principle #18)")
    parser.add_argument("--author-a", default="", help="author_id TEXT_A (D6)")
    parser.add_argument("--author-b", default="", help="author_id TEXT_B (D6)")
    parser.add_argument("--authors", metavar="FILE",
                        help="JSON {text_id: author_id} для --all-pairs (D6)")
    args = parser.parse_args(argv)

    if args.json_out:
        out_path = Path(args.json_out)
        if out_path.exists() and not args.force:
            raise SystemExit(
                f"{out_path} уже существует — используйте --force "
                f"(защита от двойного прогона, design principle #18)")

    llm = _make_llm(args.real)
    engine = CrossReferenceEngine(llm_client=llm)
    started = time.time()

    if args.all_pairs:
        directory = Path(args.all_pairs)
        files = sorted(directory.glob("*.txt"))
        if len(files) < 2:
            raise SystemExit(f"в {directory} меньше двух *.txt")
        authors: dict = {}
        if args.authors:
            authors = json.loads(Path(args.authors).read_text(encoding="utf-8"))
        records = []
        for path_i, path_j in combinations(files, 2):
            text_a = _load_pair(path_i, path_i.stem, "",
                                authors.get(path_i.stem, ""))
            text_b = _load_pair(path_j, path_j.stem, "",
                                authors.get(path_j.stem, ""))
            record = {"pair": [path_i.stem, path_j.stem], "refs": []}
            try:
                record["refs"] = engine.detect(text_a, text_a["lang"],
                                               text_b, text_b["lang"])
            except Exception as exc:  # пара помечается, прогон продолжается
                record["error"] = str(exc)[:200]
            records.append(record)
            marker = (f"  {json.dumps(record['refs'], ensure_ascii=False)}"
                      if record["refs"] else "")
            print(f"{path_i.stem} x {path_j.stem}: "
                  f"{len(record['refs'])} refs{marker}")
        total_refs = sum(len(record["refs"]) for record in records)
        print(f"\nИтого: {len(records)} пар, {total_refs} refs, "
              f"{time.time() - started:.1f}s, prompt={PROMPT_VERSION}, "
              f"usage={_usage(llm)}")
        if args.json_out:
            out = Path(args.json_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = {"prompt_version": PROMPT_VERSION,
                       "mode": "real" if args.real else "mock",
                       "records": records}
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            print(f"predictions → {out}")
        return 0

    if not args.a or not args.b:
        raise SystemExit("нужны --a и --b (или --all-pairs DIR)")
    path_a, path_b = Path(args.a), Path(args.b)
    text_a = _load_pair(path_a, args.id_a or path_a.stem, args.lang_a,
                        args.author_a)
    text_b = _load_pair(path_b, args.id_b or path_b.stem, args.lang_b,
                        args.author_b)
    refs = engine.detect(text_a, text_a["lang"], text_b, text_b["lang"])
    result = {
        "pair": [text_a["text_id"], text_b["text_id"]],
        "langs": [text_a["lang"], text_b["lang"]],
        "refs": refs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n{time.time() - started:.1f}s, prompt={PROMPT_VERSION}, "
          f"usage={_usage(llm)}")
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"prompt_version": PROMPT_VERSION,
                   "mode": "real" if args.real else "mock",
                   "records": [result]}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"result → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
