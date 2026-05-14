# Data acquisition guide

This is the concrete plan for replacing the synthetic data with real
data. Everything is organized by what feeds which scoring engine, what
the cheapest option is, what production-grade looks like, and the
order I'd actually do it in.

The pipeline reads from `data/` as CSVs. Every source listed below is
a feed that needs to land as one of those CSVs (or a Parquet — the
loader doesn't care).

---

## Quick map: what each engine needs

| Engine | Required fields | Best source |
|---|---|---|
| `vulnerability` | TSR vs peers, EV/EBITDA discount, ROIC gap, governance flags, dissent history | Bloomberg / FactSet + EDGAR proxy filings |
| `fixability` | Root-cause clarity, op levers available, M&A history | Bloomberg + earnings transcripts |
| `directors` | Tenure, independence, committee chairs, vote support, overboarding | EDGAR DEF 14A + ISS Voting Analytics |
| `claim_graph` | Same as vulnerability + qualitative narrative signal | Same + sell-side equity research |
| `shareholders` | Holder type, ownership %, governance sensitivity | 13F filings (free from EDGAR) + ISS or Glass Lewis voting records |
| `swing_shareholders` | Holder voting history + activist support history | ISS Voting Analytics (paid) |
| `legal_calendar` | Annual meeting date, nomination deadline, bylaw text | EDGAR DEF 14A + 8-K |
| `triggers` | Earnings misses, guidance cuts, CEO changes, stock drops, 13D filings | EDGAR 8-K + Bloomberg + news API |
| `proxy_advisor_shadow` | Historical ISS/GL recommendations, governance scores | ISS DataDesk + Glass Lewis subscription |
| `activist_dna` | Activist track record, fund AUM, strategy preferences | SharkRepellent (paid) + 13F + 13D filings |
| `simulation` | All of the above as inputs | (consumed only) |
| `bank_opportunity` | All of the above | (consumed only) |

---

## Tier 0: Free + immediate (do this first)

This gets you ~60% of the signal at zero cost. Limit: US public
companies only.

### EDGAR (SEC) — the foundation

Free, public, rate-limited but generous. The official APIs:

- **Submissions API**: `https://data.sec.gov/submissions/CIK{cik}.json`
  All filings for a single company, paginated.
- **Company Concept API**: `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json`
  Specific GAAP concepts (revenue, net income, etc.) across all reporting
  periods. This is your fundamentals feed.
- **Company Facts API**: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
  Everything reported by one company. Useful but big — use Company Concept
  for production.
- **Full-Text Search**: `https://efts.sec.gov/LATEST/search-index?q={query}`
  Query free-text across all filings. Useful for finding 13D/14A by date.

**Filing types to ingest:**

- **13D / 13D/A** — activist position disclosures. Required when someone
  acquires ≥5% with intent to influence. This is your activism event
  ground truth. Triggers a 10-day filing window.
- **13G / 13G/A** — passive position disclosure ≥5%. Confirms holder type.
- **13F** — quarterly institutional holdings reports (>$100M AUM).
  This is your ownership table. Filed within 45 days of quarter-end, so
  always 1-4 months stale. Fine for our purposes.
- **DEF 14A** — proxy statements. Director bios, comp tables, prior vote
  results, board committee assignments, nomination deadlines, bylaw
  references. The single richest filing for everything board-related.
- **8-K** — material events. CEO changes, earnings releases, M&A
  announcements, restatements. Your trigger feed.
- **10-K / 10-Q** — fundamentals. Better through XBRL via Company Concept
  API than parsing the document.
- **Form 4** — insider transactions. Useful for trigger detection
  (insider selling = signal).

**Implementation skeleton** (drop in `aegis/ingest/sources.py`):

```python
import requests
from time import sleep

class EDGARSource:
    BASE = "https://data.sec.gov"
    HEADERS = {"User-Agent": "Aegis Risk Analytics admin@yourdomain.com"}
    # SEC requires identifying yourself. They'll throttle if you don't.
    
    def _get(self, url):
        # SEC limit: 10 requests/sec
        resp = requests.get(url, headers=self.HEADERS)
        sleep(0.11)
        resp.raise_for_status()
        return resp.json()

    def load_company(self, cik):
        cik_padded = str(cik).zfill(10)
        return self._get(f"{self.BASE}/submissions/CIK{cik_padded}.json")
    
    def load_concept(self, cik, concept, taxonomy="us-gaap"):
        cik_padded = str(cik).zfill(10)
        return self._get(
            f"{self.BASE}/api/xbrl/companyconcept/CIK{cik_padded}/"
            f"{taxonomy}/{concept}.json"
        )
```

CIK lookup table: download once from
`https://www.sec.gov/files/company_tickers.json`. Map ticker → CIK once
on startup.

**What this gets you (mapped to scoring engines):**

| Field in pipeline | EDGAR source |
|---|---|
| `companies.dual_class_flag` | DEF 14A — search "Class A"/"Class B" with different voting rights |
| `companies.controlled_company_flag` | DEF 14A — disclosed under NYSE/Nasdaq listing rules |
| `companies.classified_board` | DEF 14A — Section on director election terms |
| `companies.annual_meeting_date` | DEF 14A — first page |
| `companies.nomination_deadline` | DEF 14A — advance notice bylaw section |
| `directors.*` | DEF 14A — director biographical table |
| `ownership.*` | 13F filings (quarterly) |
| `events.13d_filing` | 13D filings, filing_date and reporting_owner |
| `events.ceo_change` | 8-K Item 5.02 |
| `events.earnings_miss` | 8-K Item 2.02 (earnings release) + computed vs consensus |
| `events.guidance_cut` | 8-K Item 7.01 (Reg FD) |
| `financials.tsr_*` | Computed from price history (need Yahoo/Polygon for this) |

**EDGAR limits:**
- No price data — need a separate feed for TSR computation.
- No analyst estimates — need Refinitiv/FactSet for guidance-vs-consensus.
- Filings can lag actual events by hours or days.
- 10 requests/sec, no API key required, must send User-Agent header.

### Yahoo Finance (price data)

Free, no API key, scraped via `yfinance` Python package. Use it for:
- Daily price history → compute `tsr_1y_vs_peer`, `tsr_3y_vs_peer`,
  `tsr_5y_vs_peer`
- Multiples → `ev_ebitda_discount_vs_peer`, `pe_discount_vs_peer`
- Stock drops for the trigger engine

```python
import yfinance as yf
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="5y")
info = ticker.info  # PE ratio, market cap, etc.
```

Caveat: scraping is fragile. Will break when Yahoo redesigns. For
production, swap to Polygon ($29/mo) or Alpha Vantage (free tier).

### News / events feed (cheap tier)

- **GDELT** — free global news event database. Tap the API for
  trigger events (CEO change, scandals, regulatory issues). Coverage
  is broad but noisy.
- **NewsAPI** — $0 / 100 reqs day. Easy filter by company.

For production trigger detection you want Bloomberg news or Refinitiv,
but GDELT will demo well.

---

## Tier 1: Paid but worth it ($10-50K/year)

### ISS Voting Analytics — for `swing_shareholders` and `proxy_advisor`

This is the database of how every institutional holder has voted on
every proposal, going back ~15 years. Without it the swing-shareholder
engine is basically guessing.

- Vendor: ISS Corporate Solutions, DataDesk product
- Coverage: ~6,000 US companies, ~30,000 holders globally
- Price: high five to low six figures depending on coverage
- Alternative: Glass Lewis Voting Insight (cheaper, less granular)

What you load into the pipeline:
- `holder.activism_support_history` → fraction of activist resolutions
  this holder supported in last 5 years
- `holder.governance_sensitivity` → how often they vote against
  management on ESG-coded proposals
- Per-company historical PA recommendations

### SharkRepellent (FactSet) — for `activist_dna`

Database of activist campaigns globally. Goes back to 2006. Required
for the activist matching engine to be calibrated against real campaign
history.

- Vendor: FactSet (acquired SharkRepellent in 2017)
- Price: bundled into FactSet Workstation, ~$24K/year minimum
- Alternative: Insightia (formerly Activist Insight), similar coverage
  for ~$15K/year

What you load:
- `activist_archetypes` table with real activists not made-up archetypes
- `campaigns` table with thousands of real historical campaigns
  (this is the dataset you backtest against)

### Bloomberg Terminal — fundamentals + analyst data

Industry standard but expensive ($24K/year per terminal). What you
actually need from Bloomberg:
- Forward earnings estimates and consensus
- Analyst recommendations
- Industry peer groups (for vs-peer calculations)
- Reliable corporate actions (splits, M&A)

Cheaper substitutes:
- **FactSet** — similar feature set, similar price
- **S&P Capital IQ** — strong on private comps, ~$15-20K/year
- **Refinitiv Eikon** — Bloomberg alternative, ~$22K/year
- **Polygon.io / IEX Cloud** — for just market data, $30-300/mo

---

## Tier 2: Production hardening

### Real-time trigger feed

For the trigger engine to be useful, it needs to fire within minutes
of an event, not days. That means:

- **Bloomberg event streaming** — gold standard, expensive
- **Refinitiv Real-Time News** — alternative, similar pricing
- **EDGAR full-text RSS** — free, polls every 10 min. Sufficient
  for SEC filing triggers.
- **GDELT 2.0 streaming** — free, global. Use for breaking news
  outside SEC filings.
- **Twitter/X firehose** — paid via X API enterprise tier. Worth
  monitoring for early activist signals from known activist accounts.

### Activist LP capital-formation signal

The most useful leading indicator nobody has. Sources:

- **Preqin** ($30-50K/year) — fund LP databases, DDQ requests, capital
  raises. Filter for activist-strategy funds.
- **PitchBook** — similar, more PE-focused but covers activist hedge
  funds.
- **Form ADV / D filings** — free via EDGAR. New fund registrations.
- **PerTrac** — niche, for hedge fund-of-funds data.

A simple signal: in any given month, count new activist-strategy fund
launches + anchor LP commitments + Form D filings. Spikes in that
metric reliably precede campaign waves by 6-9 months.

### Activist track-record + position monitoring

- **WhaleWisdom** — free + paid tiers. Tracks 13F filings, alerts on
  new positions. ~$50/mo for the useful tier.
- **HedgeFollow** — similar, sometimes faster on new positions.
- **Insightia Vulnerability** — paid, also computes their own
  activism risk scores. Useful for benchmarking against the model.

---

## Order I'd actually do this in

If I were sitting in your seat with a budget but no real data yet:

### Week 1-2: EDGAR pipeline

1. Build a CIK → ticker → company table from the SEC's free index.
2. Implement `EDGARSource.load_companies(tickers)` that pulls:
   - latest DEF 14A (parse for board structure, governance flags,
     calendar dates)
   - latest 10-K (parse for risk factors, qualitative signal)
   - last 8 quarters of 13F holdings (build ownership table)
   - last 12 months of 8-Ks (trigger events)
   - last 5 years of 13D filings (activist history ground truth)
3. Wire it to `aegis/ingest/sources.py::EDGARSource`. Confirm the
   pipeline runs end-to-end with real data for 10 sample companies.

### Week 3: Yahoo / Polygon price layer

1. Add `yfinance` (free) or `Polygon.io` ($29/mo) for daily prices.
2. Compute TSR-vs-peer using industry-classification from EDGAR
   `SIC` codes. Use S&P 500 sector index as the peer benchmark for
   the MVP.
3. Compute valuation multiples vs peer median.

### Week 4-5: Build the real backtest

Now you have real data for ~3,000 companies and a ground-truth
campaign list from 13D filings. Run the pipeline as-of various
historical dates (use `as_of_date=` parameter) and measure:

- For companies that had 13D filings in 2023: did the model rate
  them High/Critical in 2022?
- For companies the model rated Low: how many actually had campaigns?
- For companies that had campaigns: did the model predict the
  dominant thesis correctly?

This is the moment you find out whether the weights are calibrated
correctly. They probably aren't. Re-fit them with logistic regression
on the historical data.

### Week 6+: Paid data tier (if budget allows)

In order of value-per-dollar:
1. **SharkRepellent or Insightia** ($15-24K/yr) — adds real activist
   archetypes + thousands more historical campaigns for backtesting
2. **ISS Voting Analytics** ($30K+/yr) — makes the swing-shareholder
   engine actually accurate, not just structurally plausible
3. **One real-time news feed** ($10-15K/yr for a decent one) — turns
   the trigger engine from "yesterday's news" to "alert in 5 minutes"
4. **Bloomberg / FactSet** ($24-30K/yr) — diminishing returns at this
   point unless you need M&A advisor data

---

## What the data looks like once it lands

The pipeline's `data/` dict expects these tables. Match these column
names exactly (or remap in `aegis/data/loader.py`).

### `companies` (one row per company)
```
company_id, ticker, name, sector, industry, market_cap,
annual_meeting_date, nomination_deadline,
dual_class_flag, controlled_company_flag, ceo_chair_combined,
classified_board, has_poison_pill, majority_voting_standard,
insider_ownership_pct
```

### `financials` (one row per company, vs-peer metrics)
```
company_id, tsr_1y_vs_peer, tsr_3y_vs_peer, tsr_5y_vs_peer,
ev_ebitda_discount_vs_peer, pe_discount_vs_peer,
roic_gap_vs_peer, ebitda_margin_gap_vs_peer,
capex_intensity_vs_peer, fcf_yield_vs_peer, revenue_growth_vs_peer,
mna_writeoff_history_score, guidance_miss_frequency,
earnings_miss_frequency, say_on_pay_support_pct,
director_vote_support_avg_pct
```

### `directors` (one row per director per company)
```
company_id, director_id, name, tenure_years, independent,
is_committee_chair, committee_roles, prior_vote_support_pct,
other_board_count
```

### `shareholders` (universe; not filtered per-company)
```
shareholder_id, name, holder_type, governance_sensitivity,
activism_support_history
```

### `ownership` (one row per (company, shareholder) pair)
```
company_id, shareholder_id, ownership_pct, position_change_qoq
```

### `events` (one row per event per company)
```
company_id, event_id, event_type, event_date, description, severity
```

### `campaigns` (historical activist campaigns; used as backtest truth)
```
company_id, campaign_id, activist_name, thesis_type, start_date,
board_seats_won, settled, went_to_vote, outcome, stock_reaction_30d
```

### `activist_archetypes` (one row per known activist or archetype)
```
archetype_id, name, aum_usd, typical_stake_pct, typical_seats_requested,
preferred_market_cap_min, preferred_market_cap_max,
preferred_thesis_types, campaign_style
```

### `proxy_advisor_cases` (historical PA recommendations)
```
case_id, company_id, year, iss_recommendation, gl_recommendation,
governance_concerns, pay_concerns
```

---

## Quick-start: get to "running on real data" in one afternoon

1. `pip install yfinance requests pandas`
2. Pick 20 tickers. Pull their tickers + market caps from
   `https://www.sec.gov/files/company_tickers.json`.
3. For each, hit Yahoo Finance for 5-year price history → compute
   peer-relative TSR using sector ETF (XLK, XLF, etc.) as benchmark.
4. For each, pull their latest DEF 14A from EDGAR. Don't parse it
   semantically — just look for the strings "dual-class", "controlled
   company", "classified board" to populate the bool flags. Use
   manual annotation if it's faster.
5. Skip everything that needs ISS/Bloomberg. Use synthetic shareholders
   for now.
6. Drop these into `data/*.csv` matching the schemas above.
7. Run `python smoke_test.py`. See what breaks. Fix.

You'll have real data for 20 companies powering 60% of the pipeline by
end of day. The remaining 40% (sophisticated holder data, real activist
archetypes, real proxy advisor recommendations) will need the paid tier.

---

## Compliance + licensing notes

- **EDGAR** — public-domain SEC filings. Use freely; identify yourself
  in `User-Agent`. No redistribution restrictions on the raw data.
- **13F** — already public; legal to ingest and redistribute.
- **Yahoo Finance** — scraping is in a gray area. For commercial
  production, license a real price feed.
- **ISS / Glass Lewis** — contractual; usually licensed per-seat.
  Cannot redistribute the raw recommendations to clients. Your model
  output (derived) is fine.
- **SharkRepellent / Insightia** — same; derived outputs are licensed,
  raw data is not redistributable.
- **Bloomberg** — strictest. Bloomberg data cannot be re-served via
  your own API to your clients without specific licensing.

When in doubt, derived-and-aggregated outputs ("our risk score for
TICKER is 78") are almost always fine. Raw redistribution
("TICKER's ISS voting history is X") is almost always not.
