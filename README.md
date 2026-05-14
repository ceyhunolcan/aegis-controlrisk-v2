# Aegis ControlRisk OS v2

[![CI](https://github.com/CeyhunOlcan/aegis-controlrisk-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/CeyhunOlcan/aegis-controlrisk-v2/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-orange.svg)](LICENSE)
[![Commercial use: License required](https://img.shields.io/badge/commercial%20use-license%20required-red.svg)](COMMERCIAL.md)
[![ORCID](https://img.shields.io/badge/ORCID-0000--0002--6326--6071-A6CE39?logo=orcid&logoColor=white)](https://orcid.org/0000-0002-6326-6071)

**Author:** Ceyhun Olcan
([ORCID 0000-0002-6326-6071](https://orcid.org/0000-0002-6326-6071))
— Thayer School of Engineering · Center for Technology and Behavioral
Health · Dartmouth College

> ⚠️ **Source-available, not open-source.** The code is public so you
> can read it, evaluate it, and learn from it. Running it in any
> commercial, internal-tooling, or revenue-generating context requires
> a paid license. See [LICENSE](LICENSE) and
> [COMMERCIAL.md](COMMERCIAL.md).

Aegis ControlRisk OS is an activism risk + shareholder defense
analytics engine. Pick a ticker, get back a 0-100 risk score, a
12-month event probability, the most likely activist thesis,
board-level vulnerability, a Monte Carlo proxy contest simulation, a
settle-vs-fight recommendation, and a 15-section board memo.
Everything runs locally against a synthetic dataset; no paid APIs.

The engine is called CASCADE-2. The "2" is mostly because v1 didn't
have the simulation layer.

## Quick start (evaluation only)

```bash
git clone https://github.com/CeyhunOlcan/aegis-controlrisk-v2.git
cd aegis-controlrisk-v2
pip install -r requirements.txt
make check          # runs smoke + 71 tests + 31 bug checks (~5s total)
make dashboard      # launches the Streamlit UI
```

Or use the CLI:

```bash
python aegis_cli.py analyze INDC                  # one-company summary
python aegis_cli.py batch --workers 4             # whole synthetic universe
python aegis_cli.py snapshot save INDC --note "Q3"
python aegis_cli.py alerts INDC --min-severity high
```

For commercial use, [contact us](COMMERCIAL.md).

## What's in here

```
aegis-controlrisk-v2/
├── app.py                  Streamlit dashboard - 3-layer view
├── aegis_cli.py            Command-line tool
├── smoke_test.py           End-to-end pipeline check
├── bug_test.py             Deeper regression sweep (31 checks)
├── run_tests.py            pytest-free test runner (71 tests)
├── Makefile                make check / make dashboard / etc.
├── pyproject.toml          packaging (pip install -e .)
├── requirements.txt
├── config.py
├── DATA.md                 how to wire real data sources
├── CONTRIBUTING.md         project rules + style guide
├── CHANGELOG.md
├── data/                   synthetic CSVs
├── aegis/
│   ├── pipeline.py         orchestrator everyone calls
│   ├── schemas.py
│   ├── data/               loader + synthetic generator
│   ├── scoring/            11 scoring engines
│   ├── simulation/         MC, counterfactuals, causal twin, market reaction
│   ├── reports/            memo + war room + executive view + question views
│   ├── backtesting/        runner + metrics + case study generator
│   ├── audit/              snapshots, provenance, confidence bands
│   ├── alerts/             rules + notifier
│   ├── parallel/           batch runner + disk cache
│   ├── workflow/           workspaces (multi-tenant)
│   ├── ingest/             pluggable data sources
│   └── utils/
├── tests/                  71 tests across all modules
└── .github/
    ├── workflows/ci.yml    runs the test trio on every push + PR
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

## Installing

```
pip install -r requirements.txt
```

Python 3.11+. Core deps: pandas, numpy, networkx, scipy, pydantic,
streamlit, plotly.

Pydantic is optional - if you don't have it installed, the schemas
module degrades to a thin stub and everything else still runs.

## Running

### Dashboard (interactive)

```
streamlit run app.py
```

The dashboard has three view modes in the sidebar:

- **Executive (60-sec)** — single-page landing for directors and
  principals. Verdict, top three reasons, recommended next action.
  Nothing else.
- **Question deep-dive (15-min)** — three tabs (Who / What / When)
  organized by the question being asked, not the engine producing
  the data.
- **Analyst detail (full)** — the original 16-tab layout for the
  analyst going through everything.

The sidebar also has a **Save snapshot** button. Once you have at
least one snapshot for a company, the sidebar shows any alerts that
have fired since.

### CLI (scripted)

```
python aegis_cli.py analyze INDC                  # one-company summary
python aegis_cli.py analyze INDC --json           # full JSON dict
python aegis_cli.py batch --workers 4             # run universe in parallel
python aegis_cli.py snapshot save INDC --note "Q3 close"
python aegis_cli.py snapshot list
python aegis_cli.py snapshot diff <id_old> <id_new>
python aegis_cli.py alerts INDC --min-severity high
```

Designed for cron jobs and CI pipelines. Exit codes: 0 success,
1 user error, 2 internal error.

### Smoke test

```
python smoke_test.py
```

Runs the pipeline against every company in the sample dataset. Should
take under 2 seconds and exit 0.

### Bug test

```
python bug_test.py
```

31 deeper regression checks: NaN/Inf sweep, risk-level/score
consistency, MC monotonicity, output quality, JSON-serialisability,
hidden error keys. PASS / WARN / FAIL.

### Tests

If you have pytest installed:
```
pytest -q
```

If you don't, there's a stdlib-only runner:
```
python run_tests.py
```

71 tests covering all engines, simulation determinism, settlement
game theory, claim graph, nominee matchup, swing shareholders, proxy
advisor, causal twin, bank opportunity, memo + war room, plus the
new audit / alerts / parallel / workspace / ingest / executive view /
question view modules.

### Synthetic backtest

```
python -m aegis.backtesting.backtest_runner
```

## How CASCADE-2 fits together

One function is the entry point: `aegis.pipeline.run_company_analysis(company_id, data)`.
Everything else - dashboard, memo, tests, smoke check, backtest, CLI -
reads from the dict it returns.

The pipeline runs ~32 ordered steps. Non-obvious dependencies:
- director scoring runs **before** the claim graph (claims about
  specific directors reference their scores)
- the Monte Carlo runs **twice** — once with a placeholder settlement
  pressure, again with the real value after the preliminary final
  score has computed it. Breaks the circular dependency without a
  fixed-point solver.

In v2, the pipeline also attaches:
- `confidence_bands` — bootstrap CIs on every MC probability
- `_provenance` — for vulnerability (and extensible to other scores):
  the components, weights, inputs, and data sources that produced
  the headline number

These are additive — any consumer that doesn't care just ignores
them.

## The new production layers

### Audit (`aegis/audit/`)

**Snapshots** (`snapshots.py`). Persist a full analysis to JSON
on disk, content-hashed. List, load, diff. Diffing surfaces what
moved on the headline scores between two captures of the same
company. Use it for litigation, client deliverables, "what changed
this quarter".

**Provenance** (`provenance.py`). Attach a structured record to any
score: components, weights, inputs, data sources, model version,
timestamp. `explain_score()` turns it into ranked one-line attributions.

**Confidence bands** (`confidence_bands.py`). Bootstrap CIs on MC
outputs and a data-freshness score (100 = today, 0 = >90 days old).
Use this to stop a board attorney from anchoring on a point estimate
that's actually [0.40, 0.85].

### Alerts (`aegis/alerts/`)

**Rules** (`rules.py`). Seven default rules:
- `risk_level_escalated` (critical)
- `risk_level_changed` (high)
- `risk_score_jump` ≥10 points (high)
- `nomination_deadline_imminent` ≤30 days (high)
- `new_active_trigger` (moderate)
- `activist_likely_to_win` p≥0.50 (critical)
- `high_settlement_pressure` ≥70 (high)

Rules are pure functions of (old_analysis, new_analysis). Adding a
custom rule is one tuple.

**Notifier** (`notifier.py`). Format alerts for stdout / email /
Slack Block Kit / arbitrary callback. Doesn't actually send by
default — wire your own SMTP / webhook.

### Parallel (`aegis/parallel/`)

**Batch runner** (`batch_runner.py`). Thread- or process-pool
parallel pipeline runs across a universe of companies.
Exception-isolated per company.

**Disk cache** (`disk_cache.py`). Persistent on-disk cache keyed by
(company_id, as_of_date, data_fingerprint, model_version). Bypasses
re-running the pipeline when memo writers want fresh output but the
analysis hasn't changed.

### Workflow (`aegis/workflow/`)

**Workspaces** (`workspaces.py`). Multi-tenant primitive:
- workspace → owner + members (owner / analyst / viewer roles)
- watchlist of company IDs per workspace
- free-form notes per company (permission-enforced)
- per-user alert subscriptions (severity threshold + channel)

JSON-on-disk for the MVP. The interface is the contract — swap in
Postgres later without touching consumers.

### Ingest (`aegis/ingest/`)

**Sources** (`sources.py`). Pluggable data sources. `SyntheticSource`
works today. `EDGARSource`, `BloombergSource`, `ISSSource` are
documented stubs that raise `NotImplementedError` with helpful
messages. Implement them when real-data licenses arrive.

`merge_sources(["edgar", "bloomberg", "iss"])` returns a unified
data dict; right-most source wins on conflicts.

## What the 7 sample companies look like

Each is tuned to exercise a different corner of the model.

| ID   | Profile                                   | Designed level |
|------|-------------------------------------------|----------------|
| ORCX | Energy major, transition narrative        | High           |
| INDC | Underperforming industrial conglomerate   | Critical       |
| NVTC | Stable high-performing tech               | Low            |
| MDCO | Controlled dual-class media               | Moderate (structural defenses) |
| RETR | Retail with weak margins                  | High           |
| HMED | Healthcare device, M&A speculation        | High           |
| CBNK | Bank, governance-sensitive                | High           |

MDCO is the interesting case — bad on most operational axes, but the
controlled-company + dual-class structure pins legal feasibility low
enough to land at Moderate. The model's way of saying "yes they're
terrible, no the activist can't actually win".

## Compliance

This is a model, not legal advice. The `COMPLIANCE_NOTE` in
`config.py` is propagated into every legal-calendar output, every
memo, and every war-room section. Don't strip it. The data shipped
with this repo is entirely synthetic.

## Known limitations

- Synthetic data only. Real deployment needs EDGAR + fundamentals +
  a PA transcript corpus + a curated activist-history database. The
  `aegis/ingest/` layer is wired for this; just implement the stub
  classes.
- The Monte Carlo is seeded for reproducibility. In production you'd
  want a seed-sweep ensemble for sensitivity output.
- No live triggers. Trigger detection runs on the events CSV; a real
  version would tap a streaming news/social feed.
- Workspaces are JSON-on-disk single-host. For multi-host, port to
  Postgres before adding more than ~50 workspaces.

## Roadmap

- v2.1: real EDGAR + Capital IQ ingestion behind the existing
  `aegis/ingest/` interface
- v2.2: daily background batch + email/Slack alert dispatch from
  the workspace-subscription model
- v2.3: activist-LP capital-formation signal for campaign-timing
  prediction
- v3.0: Postgres-backed workspaces, FastAPI + Next.js frontend,
  per-tenant audit log

## Licensing

Aegis ControlRisk OS is **source-available, not open-source**. The
source code is published on GitHub so you can read it, learn from it,
and evaluate whether to license it. Running it in any commercial,
internal-tooling, or revenue-generating context requires a paid
license.

- **Allowed without a license**: reading the code, forking for
  evaluation, academic research with synthetic data, submitting
  contributions
- **Requires a commercial license**: production use, internal
  deployment at any organization, integration with real data,
  embedding in a product, SaaS offering, consulting deliverables

See [LICENSE](LICENSE) for the full terms and [COMMERCIAL.md](COMMERCIAL.md)
for the commercial licensing path.

If you're not sure whether your use case requires a license, ask
first.

## Citation

If you reference this software in academic, research, evaluation, or
commercial-pitch contexts, please cite as:

> Olcan, C. (2026). *Aegis ControlRisk OS* (Version 2.0.0)
> [Computer software]. https://github.com/CeyhunOlcan/aegis-controlrisk-v2

GitHub renders a citation block from [CITATION.cff](CITATION.cff)
automatically; click "Cite this repository" on the repo page for BibTeX
or APA. ORCID: [0000-0002-6326-6071](https://orcid.org/0000-0002-6326-6071).

