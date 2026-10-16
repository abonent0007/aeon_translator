# AEON: semantic analysis and verification for Ancient Greek and Latin texts

## What it does

AEON takes a passage of Ancient Greek or Latin and produces a structured,
verifiable analysis. It extracts the meaning structure (intent, domain,
entities), identifies manuscript-level features (lacunae and other editorial
markers, fragment status), links entities to canonical identifiers (Wikidata
Q-IDs, Pleiades), and delivers language-specific morphology, fragment
reconstruction hypotheses, cross-text reference detection, and variant-reading
selection (only among editions attested in a supplied apparatus).

Every claim passes a verification layer: independent verifier agents
(grounding, fact-check, coherence) vote; below a calibrated confidence
threshold the system abstains explicitly instead of guessing. Fragment
hypotheses and cross-references are returned only after per-candidate
verification.

**Languages:** currently supports **`grc`** (Ancient Greek, period −800…600)
and **`la`** (Latin, period −200…1800). Other ancient languages (Coptic,
Sanskrit, etc.) are not supported yet.

Results are evaluated against a hand-annotated gold corpus (54 segments, 15
texts) and exported into research formats: TEI-XML (inline annotation),
Markdown, JSON-LD, BibTeX. Exports are byte-deterministic; the export tool
refuses to process gold annotations (predictions only).

## Install & run

Requires Python 3.11. From a repo checkout:

    pip install -e .
    python -m aeon.demo --text examples/greek/plato_apologia_17a.txt --verify=full --language=grc

This runs fully offline against a mock LLM. For real analysis add `--real`
(requires `DEEPSEEK_API_KEY` in `.env`); excerpt of the real output
(CLI prints in Russian, ~18 s):

    • detective grounded                         conf=1.00   all claims confirmed by exact quotes
    • logician  coherent                         conf=1.00
    CVI: 1.00 | вердикт: verified

To keep and export a result:

    python -m aeon.demo --text examples/latin/caesar_bg_1_1.txt --language=la --save-aeon out.aeon
    python -m aeon.export --aeon out.aeon --format tei --out exports/

## What's tested

- **476 tests pass; 92% coverage** (reproduce: `python tools/run_coverage.py`).
- Gold-standard baselines, reproducible from `gold/metrics.md` and
  `docs/phase3_34_report.md`: entities F1 **0.78**, detective accuracy **0.88**,
  expert/logician **1.00/1.00**, markers F1 **1.00**, morphology F1
  **0.90–0.99**, cross-reference headline link-F1 **0.800** (pilot, 105 pairs).
- Anti-leak and determinism invariants are enforced by tests (few-shot outside
  corpus, export AST-guards, gold artifacts tracked in git).

## What's not (honest)

- **Web UI/API** — none; the interface is the CLI and export formats.
  (Trigger: demonstrated external demand.)
- **Gold corpus is small** (15 texts). Calibration and external evaluation
  need expansion. (Trigger: publication claims; N≥30 for threshold calibration.)
- **Editorial markers are not persisted** into `.aeon v2` yet, so TEI
  `<gap/>`-style marker annotation is unavailable. (Trigger: TEI-marker export
  demand.)
- **Mock mode is illustrative for verification**: some canned demo responses
  predate the v1 extractor contract, so `--verify=full` under mock may abstain;
  verification-quality numbers come from real runs and gold baselines.
  (Backlog: mock-fixtures alignment.)

## How to cite

Every saved analysis is a citable artifact — generate BibTeX entries with:

    python -m aeon.export --aeon out.aeon --format bib --out exports/

producing `exports/out.aeon_artifact.bib` (your analysis, keyed by its
`atom_hash`) and `exports/out.editions.bib` (editions cited in a variant
apparatus), e.g.:

    @misc{aeon:a5812c3204, title = {AEON v2 semantic analysis: plato},
      author = {{AEON v4.0 (automated generator)}}, year = {2026},
      note = {content_hash=…; atom_hash=…; created_at=…}, ...}

## Design principles

23 recorded decisions (contract-first pipeline, validators before write,
explicit abstention, export-before-UI) — with examples and status:
`docs/phase3_retrospective.md`.

## License

- **Code:** MIT (`LICENSE`).
- **Gold annotations & metrics data:** CC0 (`gold/README.md`).
- **Example texts:** public domain, per-source notes in `examples/*/LICENSE.md`.
