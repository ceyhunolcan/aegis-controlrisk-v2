# Contributing

Glad you're here. A few things worth knowing before you open a PR.

## Setup

```bash
git clone https://github.com/<your-org>/aegis-controlrisk-v2.git
cd aegis-controlrisk-v2
python -m venv .venv && source .venv/bin/activate   # or your env manager
pip install -r requirements.txt
pip install pytest                                   # optional but recommended
```

Sanity-check before touching anything:

```bash
python smoke_test.py    # ~1s, must pass
python run_tests.py     # ~3s, must be 71/71 green
python bug_test.py      # ~2s, must be 31/31 PASS
```

## Project rules

A few things that aren't negotiable. They've all been violated at least
once and the bugs were painful enough that we now write them down:

1. **All consumers (dashboard, memo, CLI, tests, backtest) read from the
   dict returned by `aegis.pipeline.run_company_analysis()`.** Never add
   a second entry point. If you need a new view, add a new consumer of
   the same dict.

2. **The 32 pipeline steps run in a specific order.** Director scoring
   happens BEFORE the claim graph. The Monte Carlo runs TWICE (once with
   a placeholder settlement pressure, once with the real one). If you
   reorder them, the smoke test will tell you immediately. Don't fight
   it.

3. **NetworkX graphs are exported via `json_graph.node_link_data`,
   always.** Raw networkx objects don't JSON-serialize and break the
   dashboard, the snapshot system, and the disk cache.

4. **Probabilities are in [0, 1]. Scores are in [0, 100]. Vote
   percentages are 0-100.** No exceptions. The bug test verifies this
   on every numeric leaf across every company.

5. **The Monte Carlo is seeded.** Same inputs + same seed must produce
   identical outputs. The smoke test verifies this. If you introduce a
   new source of randomness, route it through the existing RNG.

6. **The `COMPLIANCE_NOTE` from `config.py` must appear in every memo,
   every legal-calendar output, every war-room section.** The bug test
   verifies it's present.

7. **All new code must read like a human wrote it.** Terse comments,
   first-person voice where appropriate, no ceremonial module docstrings,
   no `from __future__ import annotations`, no signature type hints
   unless they materially help. Comments should explain *why*, not *what*.

## Testing

### Required for any PR

- All 71 unit tests pass: `python run_tests.py` or `pytest -q`
- Smoke test passes: `python smoke_test.py`
- Bug regression sweep passes: `python bug_test.py`

CI runs all three on push.

### When adding a new scoring engine

- Add it to `aegis/scoring/`
- Wire it into `aegis/pipeline.py` at the correct position
- Add an entry to the `REQUIRED_KEYS` list in `smoke_test.py` and
  `tests/test_scoring.py`
- Add a basic shape test (output is dict, scores in range)
- Add a "this engine differentiates between companies" test (e.g.
  INDC should score differently from NVTC on whatever your engine
  measures)

### When fixing a bug

- Add a regression test BEFORE the fix
- Confirm the test fails on the bad code, then fix
- Tag the test docstring with a short note: "Regression test for
  <what> from <when>"

## Architecture notes

- `aegis/scoring/` — single-pass engines that score one company
- `aegis/simulation/` — anything that runs many samples (MC, fuzz)
- `aegis/reports/` — pure rendering layer; reads the analysis dict
- `aegis/audit/` — snapshots, provenance, confidence bands
- `aegis/alerts/` — threshold rules + notifiers
- `aegis/parallel/` — batch runner + disk cache
- `aegis/workflow/` — multi-tenant workspace primitive
- `aegis/ingest/` — pluggable data sources (synthetic + stubs for real)

No business logic in `app.py`, `aegis_cli.py`, or anything in
`aegis/reports/`. Push calculations down to `scoring/` or `simulation/`.

## Style

- Python 3.11+ syntax
- 4-space indent, no tabs
- Line length: soft 88, hard 100
- No `from __future__ import annotations` (already on 3.11+)
- Use `is None` / `is not None`, never `== None`
- Mutable default args are a bug (`def f(x=[])` will hurt you)
- Bare `except:` is never acceptable; `except Exception:` only with a
  good comment explaining why a fallback is correct

## Pull request process

1. Branch from `main`: `git checkout -b feature/your-thing`
2. Make changes
3. Run the test trio locally
4. Push and open a PR with a one-line summary + brief explanation
5. CI will run; address any failures
6. Squash on merge

## What I'd love help with

- Implement the real ingest sources (`aegis/ingest/sources.py` —
  EDGAR, Bloomberg, ISS are stubs)
- Calibrate the scoring weights against historical campaigns once
  real data is available
- Real-time trigger ingestion (currently the trigger engine reads
  from a static CSV)
- Frontend migration off Streamlit (FastAPI + Next.js suggested in
  README roadmap)
- Property-based tests via Hypothesis to complement the unit tests
- Performance work on the Monte Carlo (currently NumPy; could be
  vectorized further)

## Code of conduct

Be useful. Be specific. Be candid. Don't be precious about your code.
