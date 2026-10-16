"""CLI экспорта .aeon v2 (шаг 3.7).

Usage:
  python -m aeon.export --aeon PATH [PATH ...] --format {tei,md,jsonld,bib}
                        [--out DIR] [--label NAME] [--bib-split {on,off}]

Детерминизм: один и тот же вход → байт-идентичный выход; index.md при N>1 (Q2/E);
BibTeX split по умолчанию (Q1).
"""

import argparse
import contextlib
import sys
from pathlib import Path
from typing import List, Tuple

from .bibtex import render_bibtex_artifact, render_bibtex_editions
from .common import ExportError, load_document
from .jsonld import render_jsonld
from .markdown import render_markdown
from .tei import render_tei

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _outputs(doc, fmt: str, name: str, bib_split: str) -> List[Tuple[str, str]]:
    if fmt == "md":
        return [(f"{name}.md", render_markdown(doc, label=name))]
    if fmt == "tei":
        return [(f"{name}.tei.xml", render_tei(doc, label=name))]
    if fmt == "jsonld":
        return [(f"{name}.jsonld", render_jsonld(doc, label=name))]
    if bib_split == "on":
        return [(f"{name}.aeon_artifact.bib", render_bibtex_artifact(doc, label=name)),
                (f"{name}.editions.bib", render_bibtex_editions(doc))]
    combined = (render_bibtex_artifact(doc, label=name) + "\n"
                + render_bibtex_editions(doc))
    return [(f"{name}.bib", combined)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aeon.export")
    parser.add_argument("--aeon", nargs="+", required=True,
                        help="путь(и) к .aeon v2 (predictions)")
    parser.add_argument("--format", choices=["tei", "md", "jsonld", "bib"],
                        required=True)
    parser.add_argument("--out", default=".", help="директория вывода (Q2)")
    parser.add_argument("--label", default="",
                        help="метка для одиночного файла (по умолчанию — stem)")
    parser.add_argument("--bib-split", choices=["on", "off"], default="on")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[str] = []
    for path in args.aeon:
        source_path = Path(path)
        try:
            doc = load_document(source_path)
        except ExportError as exc:
            raise SystemExit(f"export error: {exc}") from None
        name = args.label if (args.label and len(args.aeon) == 1) \
            else source_path.stem
        for target_name, text in _outputs(doc, args.format, name,
                                          args.bib_split):
            target = out_dir / target_name
            target.write_text(text, encoding="utf-8")
            written.append(target_name)
            print(f"{source_path} → {target}")

    if len(written) > 1:
        index_lines = ["# AEON exports", ""]
        for target_name in sorted(written):
            index_lines.append(f"- [{target_name}]({target_name})")
        (out_dir / "index.md").write_text("\n".join(index_lines) + "\n",
                                          encoding="utf-8")
        print(f"index → {out_dir / 'index.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
