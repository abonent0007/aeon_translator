# LOGOS Semantic Analysis for Ancient Greek and Latin texts

LOGOS extracts structured, verified meaning from Ancient Greek (`grc`) and Latin
(`la`) passages: entities with canonical identifiers (Wikidata/Pleiades),
editorial-marker and fragment status, morphology, fragment-reconstruction
hypotheses, cross-text references, and attested variant-reading selection —
with explicit abstention when confidence is low.

- **Public summary:** `docs/aeon_public_summary.md`
- **Phase 3 retrospective (what was built, principles, honest gaps):** `docs/phase3_retrospective.md`

## Project history

- **`main` branch — legacy v3.0 archive.** The project started as
  *AEON v3.0 — Universal Meaning Translator* (author: **Abonent0007**) — an
  all-forms meaning translator (text, code, voice, images). That line is
  preserved untouched on
  [`main`](https://github.com/abonent0007/aeon_translator/tree/main).
- **`update` branch — current line (this branch).** Developed as the internal
  *v4.0 "Deep Analyst"* research line (2024–2026): contract-first pipeline,
  verification with explicit abstention, gold-standard evaluation, morphology,
  cross-reference analysis, deterministic research exports (TEI / Markdown /
  JSON-LD / BibTeX). Presented here as **LOGOS Semantic Analysis**.
- **Naming & inspiration:** inspired by the
  ["Логос 7" YouTube channel](https://www.youtube.com/@%D0%9B%D0%BE%D0%B3%D0%BE%D1%817)
  (see Acknowledgements below). Independent implementation, no affiliation.
- **Author / maintainer:** Abonent0007 · **License:** MIT.

## Quick start (Python 3.11)

    pip install -e .
    python -m aeon.demo --text examples/greek/plato_apologia_17a.txt --verify=full --language=grc

Runs fully offline with a mock LLM; add `--real` for real analysis
(requires `DEEPSEEK_API_KEY`).

## Export a result

    python -m aeon.demo --text examples/latin/caesar_bg_1_1.txt --language=la --save-aeon out.aeon
    python -m aeon.export --aeon out.aeon --format tei --out exports/

Formats: TEI-XML, Markdown, JSON-LD, BibTeX (byte-deterministic).

## Tests

    python -m pytest -q                # 476 tests
    python tools/run_coverage.py       # coverage report

## Acknowledgements

The naming of this project and its initial direction were inspired by the
["Логос 7" YouTube channel](https://www.youtube.com/@%D0%9B%D0%BE%D0%B3%D0%BE%D1%817),
which explores ancient texts through the lens of modern AI.

This project is an independent implementation — see `docs/phase3_retrospective.md`
for methodology and design principles #1–#23. No affiliation with or endorsement
by the channel is implied.

## License

MIT (code, `LICENSE`) · CC0 (gold annotations, `gold/README.md`) ·
public domain (example texts, per-source notes in `examples/*/LICENSE.md`).

## Legacy

The previous v3.0 README is preserved as `README.v3.md`.
