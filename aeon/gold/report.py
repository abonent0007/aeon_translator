"""
gold-report (шаг 3.3): markdown-отчёт метрик.

Использование:
    python -m aeon.gold.report --dataset gold/annotations/ --mode mock
    python -m aeon.gold.report --dataset gold/annotations/ --mode real
"""

import argparse
from typing import Any, Dict

from .loader import load_dataset
from .metrics import evaluate_dataset
from .runner import run_dataset


def _fmt(value: Any) -> str:
    return f"{value:.2f}" if isinstance(value, float) else str(value)


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
    parser.add_argument("--out", default=None, help="записать markdown в файл")
    args = parser.parse_args(argv)

    dataset = load_dataset(args.dataset)
    predictions = run_dataset(dataset, mode=args.mode, latency_ms=args.latency_ms)
    report = build_report(dataset, predictions)
    print(report)
    if args.out:
        from pathlib import Path

        Path(args.out).write_text(report, encoding="utf-8")
        print(f"📄 записано: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
