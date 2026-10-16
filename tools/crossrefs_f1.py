"""F1 preliminary для crossrefs (шаг 3.4.2).

Сравнивает predictions движка (JSON от `python -m aeon.crossrefs.demo
--all-pairs ... --json-out ...`) с gold cross-references (schema 1.2.0).
Buckets: high / medium / all (low исключён из всех — конвенция 3.4.1).

Usage:
  python tools/crossrefs_f1.py --predictions gold/real_runs/<run>/predictions.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aeon.gold.loader import load_dataset          # noqa: E402
from aeon.gold.metrics import cross_ref_prf        # noqa: E402


def _buckets(refs):
    keep = [ref for ref in refs
            if ref.get("confidence") in ("high", "medium")]
    return {
        "high": [ref for ref in keep if ref["confidence"] == "high"],
        "medium": [ref for ref in keep if ref["confidence"] == "medium"],
        "all": keep,
    }


def _counts(refs):
    return {level: sum(1 for ref in refs if ref.get("confidence") == level)
            for level in ("high", "medium", "low")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--dataset", default=str(ROOT / "gold" / "annotations"))
    args = parser.parse_args()

    expected = load_dataset(args.dataset).xrefs
    payload = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        print(f"prompt_version:   {payload.get('prompt_version')} "
              f"(mode={payload.get('mode')})")
        records = payload.get("records") or []
    else:
        records = payload
    predicted = [ref for record in records for ref in (record.get("refs") or [])]

    print(f"gold xrefs:       {len(expected)}  {_counts(expected)}")
    print(f"engine xrefs:     {len(predicted)}  {_counts(predicted)} "
          f"(low excluded from all buckets)")
    exp_buckets = _buckets(expected)
    pred_buckets = _buckets(predicted)
    for bucket in ("high", "medium", "all"):
        result = cross_ref_prf(exp_buckets[bucket], pred_buckets[bucket])
        per_kind = " | ".join(
            f"{kind}: f1={m['f1']:.2f} tp={m['tp']} fp={m['fp']} fn={m['fn']}"
            for kind, m in sorted(result["per_kind"].items()))
        print(f"[{bucket:6}] macro F1 {result['macro_f1']:.4f}  {per_kind}")
        link_expected = [dict(ref, kind="@link")
                         for ref in exp_buckets[bucket]]
        link_predicted = [dict(ref, kind="@link")
                          for ref in pred_buckets[bucket]]
        link = cross_ref_prf(link_expected, link_predicted)["per_kind"].get(
            "@link", {"f1": 1.0, "tp": 0, "fp": 0, "fn": 0})
        print(f"[{bucket:6}] HEADLINE link-level F1 {link['f1']:.4f}  "
              f"tp={link['tp']} fp={link['fp']} fn={link['fn']}")
    fps = [ref for ref in pred_buckets["all"]
           if not any(ref["kind"] == exp["kind"]
                      and frozenset({(ref["source"]["text_id"],
                                      ref["source"]["segment_id"]),
                                     (ref["target"]["text_id"],
                                      ref["target"]["segment_id"])})
                      == frozenset({(exp["source"]["text_id"],
                                     exp["source"]["segment_id"]),
                                    (exp["target"]["text_id"],
                                     exp["target"]["segment_id"])})
                      for exp in exp_buckets["all"])]
    print(f"\nFP list ({len(fps)}):")
    for ref in fps:
        src = f"{ref['source']['text_id']}/{ref['source']['segment_id']}"
        tgt = f"{ref['target']['text_id']}/{ref['target']['segment_id']}"
        print(f"  {src} -> {tgt} [{ref['kind']}/{ref['confidence']}] "
              f"{(ref.get('reasoning') or '')[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
