# Changelog

All notable changes to this project go in here. Keep entries terse.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2.0.0] - 2026-05-14

Initial public release.

### Added
- 32-step CASCADE-2 pipeline (`aegis.pipeline.run_company_analysis`)
- 11 scoring engines: vulnerability, fixability, directors,
  claim_graph, shareholders, swing_shareholders, legal_calendar,
  trigger_monitor, proxy_advisor_shadow, defense, settlement_game,
  final_score, bank_opportunity, activist_dna, thesis,
  nominee_matchup
- 4 simulation modules: proxy_monte_carlo, counterfactuals,
  causal_twin, market_reaction
- Reports layer: board memo (15-section), war room (red team + blue
  team + board Q&A + investor talking points + press narrative),
  executive view (60-second), question views (Who/What/When)
- Streamlit dashboard with 3-layer information architecture
  (Executive / Question deep-dive / Analyst detail)
- Command-line interface (`aegis_cli.py`) for analyze, batch,
  snapshot, alerts
- Audit layer: content-hashed snapshots, provenance tracking,
  confidence bands (bootstrap CIs), data freshness scoring
- Alert engine: 7 default rules, severity tiers, formatters for
  stdout / Slack Block Kit / email / callback
- Parallel batch runner (Thread/Process pool) + on-disk pipeline
  cache
- Multi-tenant workspaces (owner/analyst/viewer roles, watchlists,
  permission-enforced notes, per-user alert subscriptions)
- Pluggable ingest layer (synthetic source working;
  EDGAR/Bloomberg/ISS stubs documented)
- Synthetic backtesting harness: precision@k, recall@k, AUC proxy,
  calibration bins
- 71-test pytest suite (also runnable via stdlib `run_tests.py`)
- 31-check bug regression sweep
- 7-company synthetic dataset (ORCX, INDC, NVTC, MDCO, RETR, HMED,
  CBNK), 49 directors, 26 shareholders, 84 ownership rows, 8
  historical campaigns, 8 activist archetypes, 15 PA cases, 20
  events

### Fixed
- Monte Carlo scenario double-counting: the catch-all `else` in
  `proxy_monte_carlo.py` was incrementing two counters per
  simulation, inflating `scenario_counts` totals by up to 73% and
  double-counting `p_public_campaign` on every company
- `run_proxy_monte_carlo(n_simulations=0)` crashed with
  `ZeroDivisionError`; now returns safe-zero defaults
- Pipeline data lookups previously swallowed all exceptions
  silently; now narrowed to specific exception types and emit
  `warnings.warn()` for diagnostics
- NaN in director `committee_roles` field when underlying CSV had
  blank cells (loader.py fills NaN string fields with `""`)
- `risk_level` field didn't always match the composite score
  thresholds; final_score now uses `config.RISK_LEVELS` thresholds
  with an explicit escalation rule
- `run_company_analysis(None, data)` previously continued; now
  raises `ValueError` immediately

### Compliance
- `COMPLIANCE_NOTE` from `config.py` is propagated into every
  legal-calendar output, board memo, and war-room section. The bug
  test verifies presence.
- All shipped data is entirely synthetic.
