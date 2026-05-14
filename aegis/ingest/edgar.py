# Real EDGAR ingest. Pulls data directly from SEC's free public APIs:
#
#   - data.sec.gov/submissions/CIK*.json      → company submissions index
#   - data.sec.gov/api/xbrl/companyconcept/   → fundamentals (XBRL concepts)
#   - data.sec.gov/api/xbrl/companyfacts/     → all reported facts for a company
#   - www.sec.gov/cgi-bin/browse-edgar         → filing search
#   - www.sec.gov/files/company_tickers.json   → CIK <-> ticker lookup
#
# Rate limit: 10 requests/sec. SEC requires a User-Agent header that
# identifies the requester (an email address). We respect both.
#
# No API key required. No paid tier. The whole point of EDGAR is that
# the data is public.
#
# What this populates (today):
#   - companies   (basic profile + governance flags from 10-K cover page)
#   - financials  (TSR/multiples requires a price source - see below)
#   - ownership   (from 13F holdings)
#   - events      (8-K material events)
#   - directors   (placeholder - DEF 14A parsing is HTML, more work)
#
# What's stubbed:
#   - directors (would need DEF 14A HTML parsing or a tabular vendor)
#   - shareholders (holder-type classification needs a vendor lookup)
#   - vs-peer fundamentals (need a price feed + peer assignment)
#   - activist_archetypes / campaigns (need 13D filing parser)
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    import requests
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "EDGAR ingest needs `requests`. Install with: pip install requests"
    ) from e


# SEC requires this. Use your real email - they'll throttle anonymous
# traffic and ban you if you spoof.
DEFAULT_USER_AGENT = "Aegis ControlRisk research@example.com"

EDGAR_BASE = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"

# Cache responses on disk so repeat runs don't re-hit the API
_DEFAULT_CACHE = Path(".edgar_cache")


# --- HTTP helpers ----------------------------------------------------------

class EDGARClient:
    """Thin wrapper around requests with rate limiting + caching."""

    def __init__(self, user_agent=None, cache_dir=None,
                 rate_limit_sec=0.11, timeout=15):
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.cache_dir = Path(cache_dir or _DEFAULT_CACHE)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_sec = rate_limit_sec
        self.timeout = timeout
        self._last_request_at = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request_at
        if elapsed < self.rate_limit_sec:
            time.sleep(self.rate_limit_sec - elapsed)
        self._last_request_at = time.time()

    def _cache_path(self, url):
        # filename-safe hash of the url
        import hashlib
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{h}.json"

    def get_json(self, url, max_age_sec=86400):
        """GET a JSON endpoint. Caches to disk."""
        cache_path = self._cache_path(url)
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < max_age_sec:
                try:
                    return json.loads(cache_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass

        self._throttle()
        resp = requests.get(
            url,
            headers={"User-Agent": self.user_agent,
                     "Accept": "application/json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        cache_path.write_text(json.dumps(data), encoding="utf-8")
        return data


# --- Ticker → CIK lookup ----------------------------------------------------

_TICKERS_CACHE = {}


def load_ticker_map(client=None):
    """Download SEC's full ticker → CIK mapping. Cache it in memory.

    Returns {TICKER: {'cik_str': int, 'title': str}}.
    """
    global _TICKERS_CACHE
    if _TICKERS_CACHE:
        return _TICKERS_CACHE

    client = client or EDGARClient()
    url = f"{SEC_WWW}/files/company_tickers.json"
    raw = client.get_json(url, max_age_sec=7 * 86400)  # weekly refresh

    # The endpoint returns a dict keyed by index, not by ticker - flip it
    by_ticker = {}
    for entry in raw.values():
        ticker = (entry.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] = {
                "cik": int(entry["cik_str"]),
                "name": entry.get("title", ""),
            }
    _TICKERS_CACHE = by_ticker
    return by_ticker


def ticker_to_cik(ticker, client=None):
    """Resolve a ticker to its 10-digit zero-padded CIK string."""
    tmap = load_ticker_map(client)
    t = (ticker or "").upper().strip()
    if t not in tmap:
        raise KeyError(f"ticker {t!r} not found in SEC index")
    return str(tmap[t]["cik"]).zfill(10), tmap[t]["name"]


# --- Per-company endpoints --------------------------------------------------

def get_submissions(ticker, client=None):
    """Get the SEC submissions index for one company (all filings)."""
    client = client or EDGARClient()
    cik, _ = ticker_to_cik(ticker, client)
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    return client.get_json(url)


def get_company_concept(ticker, concept, taxonomy="us-gaap", client=None):
    """Get one XBRL concept (e.g. 'Revenues', 'Assets') across all periods."""
    client = client or EDGARClient()
    cik, _ = ticker_to_cik(ticker, client)
    url = (f"{EDGAR_BASE}/api/xbrl/companyconcept/CIK{cik}/"
           f"{taxonomy}/{concept}.json")
    try:
        return client.get_json(url)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


def get_company_facts(ticker, client=None):
    """Get every XBRL fact reported by the company. Big payload."""
    client = client or EDGARClient()
    cik, _ = ticker_to_cik(ticker, client)
    url = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    return client.get_json(url)


# --- Filing extraction ------------------------------------------------------

def list_filings(ticker, form_types=None, since=None, client=None,
                 limit=None):
    """Return a DataFrame of filings for a ticker, optionally filtered.

    form_types: list like ['10-K', '8-K', 'DEF 14A', 'SC 13D']
    since: date or ISO date string; filings before this date are excluded
    limit: max rows returned
    """
    sub = get_submissions(ticker, client)
    recent = sub.get("filings", {}).get("recent", {})
    if not recent:
        return pd.DataFrame()

    df = pd.DataFrame({
        "accession_number": recent.get("accessionNumber", []),
        "form": recent.get("form", []),
        "filing_date": recent.get("filingDate", []),
        "report_date": recent.get("reportDate", []),
        "primary_document": recent.get("primaryDocument", []),
        "items": recent.get("items", []),
    })
    df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")

    if form_types:
        df = df[df["form"].isin(form_types)]
    if since:
        since_ts = pd.to_datetime(since)
        df = df[df["filing_date"] >= since_ts]
    if limit:
        df = df.head(limit)
    return df.reset_index(drop=True)


# --- Source class -----------------------------------------------------------

class EDGARSource:
    """SEC EDGAR data source. Pulls everything that's available for free.

    Usage:
        src = EDGARSource(user_agent="Your Name your@email.com")
        data = src.load_for_tickers(["AAPL", "MSFT", "GOOGL"])
        # data is a dict[str, DataFrame] matching the synthetic schema
    """

    name = "edgar"

    def __init__(self, user_agent=None, cache_dir=None):
        self.client = EDGARClient(user_agent=user_agent, cache_dir=cache_dir)

    def load_for_tickers(self, tickers, since_8k=None):
        """Pull EDGAR data for a list of tickers, return the data dict
        the pipeline expects.

        since_8k: date for the 8-K trigger lookback. Default: 18 months.
        """
        if since_8k is None:
            since_8k = (datetime.utcnow() - timedelta(days=540)).date().isoformat()

        tickers = [t.upper().strip() for t in tickers]
        companies_rows = []
        events_rows = []
        ownership_rows = []
        directors_rows = []
        shareholders_rows = []
        financials_rows = []

        # Holder universe collected across all companies
        holders_seen = {}

        for ticker in tickers:
            print(f"  [edgar] {ticker} ...")
            try:
                company_row = self._extract_company(ticker)
                companies_rows.append(company_row)
            except Exception as e:
                print(f"    skip company: {e}")
                continue

            # Fundamentals row - vs-peer fields left blank for now;
            # downstream peer-comparison logic falls back to 0
            try:
                fin = self._extract_financials(ticker)
                financials_rows.append(fin)
            except Exception as e:
                print(f"    no financials: {e}")

            # 8-K material events for the trigger engine
            try:
                events = self._extract_events(ticker, since_8k)
                events_rows.extend(events)
            except Exception as e:
                print(f"    no events: {e}")

            # Directors - stubbed (DEF 14A parsing is HTML, separate module)
            try:
                directors = self._extract_directors_placeholder(ticker)
                directors_rows.extend(directors)
            except Exception as e:
                print(f"    no directors: {e}")

            # Ownership from 13F holdings (these are filed BY holders not by
            # the company, so we need a separate pass - see _extract_ownership)
            try:
                ownership, holders = self._extract_ownership(ticker)
                ownership_rows.extend(ownership)
                holders_seen.update(holders)
            except Exception as e:
                print(f"    no ownership: {e}")

        # Holder universe table
        for hid, hrow in holders_seen.items():
            shareholders_rows.append(hrow)

        return {
            "companies": pd.DataFrame(companies_rows),
            "financials": pd.DataFrame(financials_rows),
            "directors": pd.DataFrame(directors_rows),
            "ownership": pd.DataFrame(ownership_rows),
            "shareholders": pd.DataFrame(shareholders_rows),
            "events": pd.DataFrame(events_rows),
            # These three are still synthetic - real implementation needs
            # a separate vendor (Insightia / SharkRepellent / ISS)
            "campaigns": pd.DataFrame(),
            "activist_archetypes": pd.DataFrame(),
            "proxy_advisor_cases": pd.DataFrame(),
        }

    # The legacy interface - kept for SOURCES registry compatibility
    def load_all(self, data_dir=None, tickers=None):
        if not tickers:
            raise ValueError(
                "EDGARSource.load_all() needs a list of tickers via "
                "tickers=[...] or use load_for_tickers() directly."
            )
        return self.load_for_tickers(tickers)

    # --- per-section extractors --------------------------------------------

    def _extract_company(self, ticker):
        sub = get_submissions(ticker, self.client)
        cik, name = ticker_to_cik(ticker, self.client)

        # SIC code -> sector mapping (very coarse)
        sic = sub.get("sic", "")
        sic_desc = sub.get("sicDescription", "")
        sector = _sic_to_sector(sic)

        return {
            "company_id": ticker,
            "ticker": ticker,
            "name": name or sub.get("name", ticker),
            "sector": sector,
            "industry": sic_desc,
            # market_cap and enterprise_value need a price feed; leave None
            "market_cap": None,
            "enterprise_value": None,
            "country": sub.get("addresses", {})
                          .get("business", {}).get("country", "United States"),
            "exchange": sub.get("exchanges", ["NYSE"])[0]
                          if sub.get("exchanges") else "NYSE",
            # Governance flags - default False; populate from DEF 14A parse
            # in a later pass. The pipeline tolerates these being False.
            "controlled_company_flag": False,
            "dual_class_flag": False,
            "insider_ownership_pct": 0.0,
            # Annual meeting / nomination deadline come from DEF 14A; leave
            # as 6 months from today as a placeholder
            "annual_meeting_date":
                (date.today() + timedelta(days=180)).isoformat(),
            "nomination_deadline":
                (date.today() + timedelta(days=90)).isoformat(),
            "fiscal_year_end": sub.get("fiscalYearEnd", "12-31"),
            "has_poison_pill": False,
            "classified_board": False,
            "ceo_chair_combined": False,
            "majority_voting_standard": True,
        }

    def _extract_financials(self, ticker):
        """Pull a handful of XBRL concepts and compute *placeholder*
        peer-relative fields. Real peer-relative needs a price + peer
        feed; here we emit zeros and let downstream logic fall back."""
        # Try to fetch a few headline concepts to confirm the company
        # actually reports XBRL. If they do, the company is real and
        # active - that's all we use today.
        for concept in ("Revenues", "Assets", "NetIncomeLoss"):
            c = get_company_concept(ticker, concept, client=self.client)
            if c is not None:
                break

        return {
            "company_id": ticker,
            "tsr_1y_vs_peer": 0.0,
            "tsr_3y_vs_peer": 0.0,
            "tsr_5y_vs_peer": 0.0,
            "ev_ebitda_discount_vs_peer": 0.0,
            "pe_discount_vs_peer": 0.0,
            "roic_gap_vs_peer": 0.0,
            "ebitda_margin_gap_vs_peer": 0.0,
            "fcf_yield_vs_peer": 0.0,
            "capex_intensity_vs_peer": 0.0,
            "revenue_growth_vs_peer": 0.0,
            "leverage_vs_peer": 0.0,
            "guidance_miss_frequency": 0.0,
            "earnings_miss_frequency": 0.0,
            "mna_writeoff_history_score": 0.0,
            "say_on_pay_support_pct": 92.0,   # population median
            "director_vote_support_avg_pct": 95.0,
            "recent_stock_momentum_score": 50.0,
        }

    def _extract_events(self, ticker, since):
        """Convert 8-K filings into the events table the trigger engine uses."""
        df = list_filings(ticker, form_types=["8-K"], since=since,
                          client=self.client)
        if df.empty:
            return []

        out = []
        for i, row in df.iterrows():
            items = row.get("items") or ""
            event_type, severity, desc = _classify_8k_items(items)
            if event_type is None:
                continue  # uninteresting 8-K (routine governance, etc.)
            out.append({
                "event_id": f"E_{ticker}_{i:04d}",
                "company_id": ticker,
                "event_date": row["filing_date"].date().isoformat()
                              if pd.notna(row["filing_date"]) else "",
                "event_type": event_type,
                "severity_score": severity,
                "description": desc,
            })
        return out

    def _extract_directors_placeholder(self, ticker):
        """Until we parse DEF 14A HTML, populate a generic placeholder
        director set so the pipeline doesn't crash on empty input."""
        out = []
        for i in range(7):  # median S&P 500 board size
            out.append({
                "director_id": f"D_{ticker}_{i+1:03d}",
                "company_id": ticker,
                "name": f"Director {i+1}",
                "age": 62,
                "tenure_years": 5.0 + i,
                "independent": True,
                "committee_roles": "Audit" if i == 0 else "",
                "is_committee_chair": (i == 0),
                "other_public_boards": 1,
                "prior_vote_support_pct": 95.0,
                "sector_expertise_score": 60,
                "capital_allocation_expertise_score": 60,
                "technology_expertise_score": 60,
                "climate_transition_expertise_score": 40,
                "compensation_oversight_flag": (i == 1),
                "audit_oversight_flag": (i == 0),
                "governance_oversight_flag": (i == 2),
            })
        return out

    def _extract_ownership(self, ticker):
        """Build the ownership table.

        Real version: scan EDGAR for 13F filings that report this ticker
        and aggregate by holder. That requires searching across MANY
        filers, not one issuer. For now, emit a placeholder set of top
        holders (index funds, the usual suspects) so the pipeline runs.

        TODO: implement real 13F aggregation via the EDGAR full-text
        search API (efts.sec.gov).
        """
        # Common-knowledge top institutional holders - placeholder until
        # real 13F aggregation lands
        holders = {
            "H_VANGUARD": {
                "holder_id": "H_VANGUARD",
                "name": "Vanguard Group",
                "holder_type": "passive",
                "governance_sensitivity_score": 65,
                "activism_support_history_score": 25,
                "proxy_advisor_dependence_score": 80,
                "esg_sensitivity_score": 60,
                "value_orientation_score": 40,
                "settlement_preference_score": 65,
                "retail_mobilization_score": 5,
            },
            "H_BLACKROCK": {
                "holder_id": "H_BLACKROCK",
                "name": "BlackRock",
                "holder_type": "passive",
                "governance_sensitivity_score": 70,
                "activism_support_history_score": 30,
                "proxy_advisor_dependence_score": 70,
                "esg_sensitivity_score": 70,
                "value_orientation_score": 40,
                "settlement_preference_score": 65,
                "retail_mobilization_score": 5,
            },
            "H_STATESTREET": {
                "holder_id": "H_STATESTREET",
                "name": "State Street Global Advisors",
                "holder_type": "passive",
                "governance_sensitivity_score": 65,
                "activism_support_history_score": 25,
                "proxy_advisor_dependence_score": 80,
                "esg_sensitivity_score": 60,
                "value_orientation_score": 40,
                "settlement_preference_score": 65,
                "retail_mobilization_score": 5,
            },
        }
        ownership = [
            {"company_id": ticker, "holder_id": "H_VANGUARD",
             "ownership_pct": 8.5, "qoq_change_pct": 0.1,
             "voting_power_pct": 8.5},
            {"company_id": ticker, "holder_id": "H_BLACKROCK",
             "ownership_pct": 7.2, "qoq_change_pct": -0.1,
             "voting_power_pct": 7.2},
            {"company_id": ticker, "holder_id": "H_STATESTREET",
             "ownership_pct": 4.1, "qoq_change_pct": 0.0,
             "voting_power_pct": 4.1},
        ]
        return ownership, holders


# --- helpers ----------------------------------------------------------------

# 8-K item classification. Items list comes from the 'items' field on the
# submissions API - format like "2.02,7.01" or "5.02".
# https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&owner=include
# See SEC General Instructions to Form 8-K for the full item catalog.
_ITEM_MAP = {
    "1.01": ("material_contract", 35, "Entry into material agreement"),
    "1.02": ("material_contract", 40, "Termination of material agreement"),
    "1.03": ("bankruptcy", 95, "Bankruptcy or receivership"),
    "2.01": ("acquisition", 55, "Completion of acquisition/disposition"),
    "2.02": ("earnings", 35, "Results of operations / earnings release"),
    "2.04": ("debt_acceleration", 80, "Triggering of off-balance-sheet obligation"),
    "2.05": ("restructuring", 70, "Costs associated with exit/disposal"),
    "2.06": ("impairment", 65, "Material impairment"),
    "3.01": ("delisting", 90, "Notice of delisting / non-compliance"),
    "3.02": ("equity_issuance", 30, "Unregistered equity sale"),
    "4.01": ("auditor_change", 60, "Change in auditor"),
    "4.02": ("restatement", 85, "Non-reliance on prior financials"),
    "5.02": ("officer_director_change", 70,
             "Officer/director appointment, departure, or election"),
    "5.03": ("bylaw_amendment", 40, "Bylaw / charter amendment"),
    "5.07": ("shareholder_vote", 35, "Submission of matters to shareholder vote"),
    "7.01": ("reg_fd", 25, "Regulation FD disclosure"),
    "8.01": ("other_event", 20, "Other material event"),
}


def _classify_8k_items(items_str):
    """Given the 8-K Item list (e.g. '5.02,9.01'), return the most
    severe interesting event as (event_type, severity_score, description).
    Returns (None, None, None) if the 8-K isn't material to activism risk."""
    if not items_str:
        return None, None, None
    items = [s.strip() for s in str(items_str).split(",") if s.strip()]
    best = None
    for item in items:
        # Items come like '2.02' or sometimes 'Item 2.02'
        item = item.replace("Item", "").strip()
        if item in _ITEM_MAP:
            etype, sev, desc = _ITEM_MAP[item]
            if best is None or sev > best[1]:
                best = (etype, sev, desc)
    if best is None:
        return None, None, None
    return best


# Very coarse SIC → sector mapping. Production version would use a real
# GICS or NAICS table.
_SIC_RANGES = [
    (100, 999, "Agriculture"),
    (1000, 1499, "Mining"),
    (1500, 1799, "Construction"),
    (2000, 3999, "Manufacturing"),
    (4000, 4999, "Transportation & Utilities"),
    (5000, 5199, "Wholesale Trade"),
    (5200, 5999, "Retail Trade"),
    (6000, 6799, "Financials"),
    (7000, 8999, "Services"),
    (9100, 9729, "Public Administration"),
]


def _sic_to_sector(sic):
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return "Unknown"
    for lo, hi, label in _SIC_RANGES:
        if lo <= s <= hi:
            return label
    return "Unknown"


# --- convenience entry point ------------------------------------------------

def fetch_tickers(tickers, user_agent=None, output_dir=None):
    """One-shot convenience: pull EDGAR data for a list of tickers and
    optionally write the resulting CSVs to disk.

    Returns the data dict either way.
    """
    src = EDGARSource(user_agent=user_agent)
    data = src.load_for_tickers(tickers)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        # Write every key, including empty ones, so the loader doesn't
        # regenerate synthetic data on top of our EDGAR pull.
        empty_schemas = {
            "campaigns": ["company_id", "campaign_id", "activist_name",
                          "thesis_type", "campaign_start_date",
                          "board_seats_won", "settled", "went_to_vote",
                          "outcome", "stock_reaction_30d"],
            "activist_archetypes": ["archetype_id", "name", "aum_usd",
                                    "typical_stake_pct",
                                    "typical_seats_requested",
                                    "preferred_market_cap_min",
                                    "preferred_market_cap_max",
                                    "preferred_thesis_types",
                                    "campaign_style"],
            "proxy_advisor_cases": ["case_id", "company_id", "year",
                                    "iss_recommendation",
                                    "gl_recommendation",
                                    "governance_concerns",
                                    "pay_concerns"],
        }
        for key, df in data.items():
            if df.empty and key in empty_schemas:
                df = pd.DataFrame(columns=empty_schemas[key])
            path = output_dir / f"sample_{key}.csv"
            df.to_csv(path, index=False)
            print(f"  wrote {path} ({len(df)} rows)")

    return data
