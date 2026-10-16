# AEON — semantic analysis and verification for Ancient Greek and Latin texts

AEON extracts structured, verified meaning from Ancient Greek (`grc`) and Latin
(`la`) passages: entities with canonical identifiers (Wikidata/Pleiades),
editorial-marker and fragment status, morphology, fragment-reconstruction
hypotheses, cross-text references, and attested variant-reading selection —
with explicit abstention when confidence is low.

- **Public summary:** `docs/aeon_public_summary.md`
- **Phase 3 retrospective (what was built, principles, honest gaps):** `docs/phase3_retrospective.md`

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

## License

MIT (code, `LICENSE`) · CC0 (gold annotations, `gold/README.md`) ·
public domain (example texts, per-source notes in `examples/*/LICENSE.md`).

## Legacy

The previous v3.0 README is preserved as `README.v3.md`.
