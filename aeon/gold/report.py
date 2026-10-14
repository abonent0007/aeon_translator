"""
gold-report (шаг 3.3): markdown-отчёт метрик + cost/latency (2.7.7).

Использование:
    python -m aeon.gold.report --dataset gold/annotations/ --mode mock
    python -m aeon.gold.report --dataset gold/annotations/ --mode real \
        --raw-dir gold/real_runs/<ts> [--out report.md]
    python -m aeon.gold.report --dataset gold/annotations/ --dry-run
"""

import argparse
from typing import Any, Dict

from ..config import CONFIG
from .loader import load_dataset
from .metrics import evaluate_dataset
from .runner import _make_llm, run_dataset


def _fmt(value: Any) -> str:
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def planned_calls(dataset) -> Dict[str, int]:
    """Dry-run: сколько LLM-вызовов потребует real-прогон (без вызовов API)."""
    verdict_records = [record for record in dataset.records
                       if record.expected_verdicts is not None]
    return {
        "segments": len(dataset.records),
        "extract_calls": len(dataset.records),
        "verdict_records": len(verdict_records),
        "verify_calls": len(verdict_records) * 3,
        "total": len(dataset.records) + len(verdict_records) * 3,
    }


def format_cost_block(stats: Dict[str, Any], usage: Dict[str, Any]) -> str:
    """Cost/latency-блок (2.7.7): факт из usage-счётчиков провайдера."""
    cost = ((usage.get("prompt_tokens", 0) / 1_000_000) * CONFIG.llm.price_in_per_m
            + (usage.get("completion_tokens", 0) / 1_000_000) * CONFIG.llm.price_out_per_m)
    return "\n".join([
        "",
        "## Cost / latency (2.7.7)",
        "",
        f"- LLM-вызовов: {stats.get('calls', 0)}",
        f"- tokens in/out: {usage.get('prompt_tokens', 0)}/{usage.get('completion_tokens', 0)}",
        f"- **cost: ${cost:.4f}** (тариф {CONFIG.llm.price_in_per_m}/"
        f"{CONFIG.llm.price_out_per_m} USD за 1M in/out — дефолт, env-настраиваемый)",
        f"- latency: {stats.get('latency_sec', 'n/a')} s total",
    ]) + "\n"


def format_run_details(dataset, stats: Dict[str, Any]) -> str:
    """Per-text run-таблица + failures (2.7.3)."""
    lines = ["", "## Per-text runs", "",
             "| text_id | segments | extract (план) | verify (план) | calls | "
             "latency s | cost $ |",
             "|---|---|---|---|---|---|---|"]
    total_cost = 0.0
    for text_id, records in sorted(dataset.by_text().items()):
        verdict_records = sum(1 for record in records
                              if record.expected_verdicts is not None)
        entry = stats.get("per_text", {}).get(text_id, {})
        cost = ((entry.get("prompt_tokens", 0) / 1_000_000) * CONFIG.llm.price_in_per_m
                + (entry.get("completion_tokens", 0) / 1_000_000) * CONFIG.llm.price_out_per_m)
        total_cost += cost
        lines.append(
            f"| {text_id} | {len(records)} | {len(records)} | "
            f"{verdict_records * 3} | {entry.get('calls', 0)} | "
            f"{entry.get('latency_sec', 0)} | ${cost:.4f} |")
    lines.append(f"| **TOTAL** | **{len(dataset.records)}** | | | "
                 f"**{stats.get('calls', 0)}** | **{stats.get('latency_sec', 'n/a')}** | "
                 f"**${total_cost:.4f}** |")
    failures = stats.get("failures", [])
    if failures:
        lines += ["", "## Failures", ""]
        lines += [f"- {failure['text_id']} seg {failure['segment_id']}: "
                  f"{failure['error']}" for failure in failures]
    return "\n".join(lines) + "\n"


def build_report(dataset, predictions: Dict[str, Any]) -> str:
    evaluation = evaluate_dataset(dataset, predictions)
    lines = [
        "# AEON gold-standard report",
        "",
        f"Записей: {evaluation['aggregate']['segments']} | "
        f"схема: {dataset.version()} | режим: mock/real (см. команду)",
        "",
        "## Aggregate",
        "",
        "| метрика | значение |",
        "|---|---|",
    ]
    aggregate = evaluation["aggregate"]
    for kind, metrics in sorted(aggregate["markers"]["per_kind"].items()):
        lines.append(f"| Markers F1 ({kind}) | {_fmt(metrics['f1'])} "
                     f"(P {_fmt(metrics['precision'])} / R {_fmt(metrics['recall'])}) |")
    lines.append(f"| Markers macro F1 | {_fmt(aggregate['markers']['macro_f1'])} |")
    lines.append(f"| Entities F1 | {_fmt(aggregate['entities']['f1'])} "
                 f"(P {_fmt(aggregate['entities']['precision'])} / "
                 f"R {_fmt(aggregate['entities']['recall'])}) |")
    lines.append(f"| is_fragment accuracy | {_fmt(aggregate['is_fragment_accuracy'])} |")
    lines.append(f"| completeness MAE | {_fmt(aggregate['completeness_mae'])} |")
    for agent, accuracy in sorted(aggregate["verdicts"].items()):
        lines.append(f"| Verdict accuracy ({agent}) | {_fmt(accuracy)} |")

    lines += ["", "## Per text", "",
              "| text_id | seg | markers macro F1 | entities F1 | frag acc | "
              "compl MAE | verdicts |",
              "|---|---|---|---|---|---|---|"]
    for text_id, metrics in sorted(evaluation["per_text"].items()):
        verdicts = ", ".join(f"{agent}:{_fmt(acc)}"
                             for agent, acc in sorted(metrics["verdicts"].items())) or "—"
        lines.append(
            f"| {text_id} | {metrics['segments']} | "
            f"{_fmt(metrics['markers']['macro_f1'])} | "
            f"{_fmt(metrics['entities']['f1'])} | "
            f"{_fmt(metrics['is_fragment_accuracy'])} | "
            f"{_fmt(metrics['completeness_mae'])} | {verdicts} |")

    lines += ["", "## Per text × kind (markers F1)", "",
              "| text_id | " + " | ".join(sorted(
                  {kind for metrics in evaluation["per_text"].values()
                   for kind in metrics["markers"]["per_kind"]})) + " |",
              "|---" * (2 + len({kind for metrics in evaluation["per_text"].values()
                                 for kind in metrics["markers"]["per_kind"]})) + "|"]
    all_kinds = sorted({kind for metrics in evaluation["per_text"].values()
                        for kind in metrics["markers"]["per_kind"]})
    for text_id, metrics in sorted(evaluation["per_text"].items()):
        cells = []
        for kind in all_kinds:
            entry = metrics["markers"]["per_kind"].get(kind)
            cells.append(_fmt(entry["f1"]) if entry else "—")
        lines.append(f"| {text_id} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AEON gold-standard report (шаг 3.3)")
    parser.add_argument("--dataset", default="gold/annotations",
                        help="директория с *.jsonl аннотациями")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--latency-ms", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true",
                        help="оценка числа LLM-вызовов без запросов к API")
    parser.add_argument("--raw-dir", default=None,
                        help="сохранять сырые LLM-ответы (аудит real-прогонов)")
    parser.add_argument("--out", default=None, help="записать markdown в файл")
    args = parser.parse_args(argv)

    dataset = load_dataset(args.dataset)

    if args.dry_run:
        plan = planned_calls(dataset)
        print("DRY-RUN (без вызовов API):")
        print(f"  extract: {plan['extract_calls']} вызовов "
              f"({plan['segments']} сегментов)")
        print(f"  verify:  {plan['verify_calls']} вызовов "
              f"({plan['verdict_records']} записей × 3 агента)")
        print(f"  ИТОГО:   {plan['total']} вызовов; стоимость измеряется "
              f"live (tracking 2.7.7); стоп-порог: >$2 → стоп")
        return 0

    llm = _make_llm(args.mode, args.latency_ms)
    stats: Dict[str, Any] = {}
    predictions = run_dataset(dataset, llm=llm, raw_dir=args.raw_dir, stats=stats)
    report = build_report(dataset, predictions)
    report += format_run_details(dataset, stats)
    usage = dict(getattr(llm, "usage", {}) or {})
    report += format_cost_block(stats, usage)
    if args.raw_dir:
        report += f"\nRaw-ответы: `{args.raw_dir}`\n"
    print(report)
    if args.out:
        from pathlib import Path

        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        print(f"📄 записано: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
