# Yahoo Finance ingest. Pulls daily prices and computes peer-relative
# fundamentals that the EDGAR ingest can't (no price data in SEC filings).
#
# Why Yahoo: free, no API key, broad coverage. The yfinance package
# scrapes Yahoo's website so it occasionally breaks when Yahoo redesigns,
# but for an MVP it's the right tradeoff. Production would swap to
# Polygon ($29/mo) or Alpha Vantage with one method change.
#
# What this populates:
#   - Real market cap and enterprise value (companies table)
#   - tsr_1y / tsr_3y / tsr_5y vs peer median (financials table)
#   - ev_ebitda_discount vs peer (financials table)
#   - pe_discount vs peer (financials table)
#   - recent_stock_momentum_score (financials table)
#
# Peer assignment: same SIC group from EDGAR, top-N by market cap.
# Crude but works. Production would use GICS sub-industry from Bloomberg.
import math
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

# yfinance is optional - we fail loudly only when the user actually calls
# the ingest. Importing the module itself is cheap.
try:
    import yfinance as yf
    _HAS_YFINANCE = True
except ImportError:
    _HAS_YFINANCE = False


# Default peer universes by SIC range. These are coarse but good enough
# to compute meaningful peer-relative TSR. The user can override via
# the peer_tickers= parameter.
_DEFAULT_PEER_UNIVERSE = {
    "tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMZN", "CRM",
             "ORCL", "ADBE", "INTC", "AMD", "QCOM", "CSCO", "IBM"],
    "financials": ["JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "PNC",
                   "TFC", "COF", "AXP", "BLK", "SCHW"],
    "energy": ["XOM", "CVX", "COP", "EOG", "OXY", "MPC", "PSX", "VLO",
               "SLB", "HAL", "BKR"],
    "healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO",
                   "DHR", "ABT", "BMY", "AMGN", "GILD"],
    "consumer": ["WMT", "COST", "PG", "KO", "PEP", "HD", "MCD", "NKE",
                 "SBUX", "TGT", "LOW", "DIS"],
    "industrials": ["GE", "BA", "CAT", "HON", "UPS", "RTX", "LMT", "DE",
                    "MMM", "EMR", "ETN", "ITW"],
}


def _peers_for_sic(sic):
    """Map an SIC code to a coarse peer set. Returns a list of tickers."""
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return _DEFAULT_PEER_UNIVERSE["tech"]  # default fallback
    if 6000 <= s <= 6799:
        return _DEFAULT_PEER_UNIVERSE["financials"]
    if 1300 <= s <= 2999 or 2900 <= s <= 2999:
        return _DEFAULT_PEER_UNIVERSE["energy"]
    if 2830 <= s <= 2836 or 8000 <= s <= 8099 or s == 3841:
        return _DEFAULT_PEER_UNIVERSE["healthcare"]
    if 5200 <= s <= 5999 or 2000 <= s <= 2199 or 5800 <= s <= 5899:
        return _DEFAULT_PEER_UNIVERSE["consumer"]
    if 3500 <= s <= 3899 or 1500 <= s <= 1799:
        return _DEFAULT_PEER_UNIVERSE["industrials"]
    return _DEFAULT_PEER_UNIVERSE["tech"]


def _require_yfinance():
    if not _HAS_YFINANCE:
        raise ImportError(
            "Yahoo Finance ingest needs `yfinance`. Install with: "
            "pip install yfinance"
        )


def get_price_history(ticker, period="5y"):
    """Return a DataFrame of [date, close, volume] for one ticker.

    period: '1mo' / '3mo' / '6mo' / '1y' / '2y' / '5y' / '10y' / 'max'
    """
    _require_yfinance()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=period, auto_adjust=True)
            if hist.empty:
                return pd.DataFrame()
            return hist.reset_index()[["Date", "Close", "Volume"]].rename(
                columns={"Date": "date", "Close": "close", "Volume": "volume"}
            )
        except Exception:
            return pd.DataFrame()


def get_company_info(ticker):
    """Pull current snapshot fundamentals from Yahoo."""
    _require_yfinance()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            return {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "roic": info.get("returnOnEquity"),  # proxy
                "operating_margin": info.get("operatingMargins"),
                "revenue_growth": info.get("revenueGrowth"),
                "free_cashflow": info.get("freeCashflow"),
                "beta": info.get("beta"),
                "shares_short": info.get("sharesShort"),
                "held_pct_insiders": info.get("heldPercentInsiders"),
                "held_pct_institutions": info.get("heldPercentInstitutions"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            }
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}


def compute_tsr(price_df, lookback_years):
    """Total return over lookback_years from a daily price series.

    Returns a percentage (e.g. -12.5 for -12.5%). Returns None if there's
    insufficient data.
    """
    if price_df is None or price_df.empty:
        return None
    df = price_df.sort_values("date").reset_index(drop=True)
    if len(df) < 2:
        return None
    end_date = df["date"].iloc[-1]
    start_target = end_date - pd.Timedelta(days=int(365 * lookback_years))
    # nearest available trading day on/after the target
    earlier = df[df["date"] <= start_target]
    if earlier.empty:
        return None
    start_price = float(earlier.iloc[-1]["close"])
    end_price = float(df.iloc[-1]["close"])
    if start_price <= 0:
        return None
    return round(((end_price / start_price) - 1.0) * 100.0, 2)


def compute_momentum_score(price_df):
    """Compute a 0-100 momentum score from the last 6 months of returns.

    Higher = more positive momentum (less vulnerable to activism).
    """
    if price_df is None or price_df.empty:
        return 50.0
    df = price_df.sort_values("date").reset_index(drop=True)
    if len(df) < 30:
        return 50.0
    end_price = float(df.iloc[-1]["close"])
    # 6-month lookback
    cutoff = df["date"].iloc[-1] - pd.Timedelta(days=180)
    earlier = df[df["date"] <= cutoff]
    if earlier.empty:
        return 50.0
    start_price = float(earlier.iloc[-1]["close"])
    if start_price <= 0:
        return 50.0
    ret = (end_price / start_price) - 1.0
    # Map -50% return -> 0, +50% return -> 100, linear in between
    score = 50.0 + (ret / 0.50) * 50.0
    return float(max(0.0, min(100.0, score)))


def fetch_peer_universe(peer_tickers, period="5y", verbose=False):
    """Fetch price history + info for a peer set. Returns dict keyed by
    ticker with {history, info, tsr_1y, tsr_3y, tsr_5y, ev_ebitda,
    trailing_pe, momentum}."""
    out = {}
    for t in peer_tickers:
        if verbose:
            print(f"    peer {t}...")
        hist = get_price_history(t, period=period)
        info = get_company_info(t)
        out[t] = {
            "history": hist,
            "info": info,
            "tsr_1y": compute_tsr(hist, 1),
            "tsr_3y": compute_tsr(hist, 3),
            "tsr_5y": compute_tsr(hist, 5),
            "ev_ebitda": info.get("ev_ebitda"),
            "trailing_pe": info.get("trailing_pe"),
            "momentum": compute_momentum_score(hist),
        }
    return out


def _median(values):
    """Median of a list, ignoring None/NaN."""
    clean = [float(v) for v in values
             if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not clean:
        return None
    return float(np.median(clean))


def enrich_with_yahoo(ticker, sic=None, peer_tickers=None,
                     verbose=False):
    """For one ticker, pull Yahoo data and compute peer-relative metrics.

    Returns a dict with fields ready to merge into the financials and
    companies tables.

    sic: optional SIC code from EDGAR for default peer assignment.
    peer_tickers: optional explicit peer list; overrides sic-based default.
    """
    _require_yfinance()
    if verbose:
        print(f"  [yahoo] {ticker}...")

    target_hist = get_price_history(ticker, period="5y")
    target_info = get_company_info(ticker)

    if not peer_tickers:
        peer_tickers = _peers_for_sic(sic)
    # Exclude self from peer set
    peer_tickers = [p for p in peer_tickers if p.upper() != ticker.upper()]

    if verbose:
        print(f"    peers: {peer_tickers}")
    peers = fetch_peer_universe(peer_tickers, period="5y", verbose=verbose)

    peer_tsr_1y = _median([p["tsr_1y"] for p in peers.values()])
    peer_tsr_3y = _median([p["tsr_3y"] for p in peers.values()])
    peer_tsr_5y = _median([p["tsr_5y"] for p in peers.values()])
    peer_ev_ebitda = _median([p["ev_ebitda"] for p in peers.values()])
    peer_pe = _median([p["trailing_pe"] for p in peers.values()])

    target_tsr_1y = compute_tsr(target_hist, 1)
    target_tsr_3y = compute_tsr(target_hist, 3)
    target_tsr_5y = compute_tsr(target_hist, 5)
    target_ev_ebitda = target_info.get("ev_ebitda")
    target_pe = target_info.get("trailing_pe")
    target_momentum = compute_momentum_score(target_hist)

    def _gap(target, peer):
        if target is None or peer is None:
            return 0.0
        try:
            return round(float(target) - float(peer), 2)
        except (TypeError, ValueError):
            return 0.0

    def _multiple_discount(target, peer):
        # For multiples we want "discount vs peer" - lower than peer
        # is more vulnerable (cheaper, potentially undervalued)
        if target is None or peer is None or peer == 0:
            return 0.0
        try:
            return round(((float(target) - float(peer)) / float(peer)) * 100.0, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    return {
        "ticker": ticker,
        # market cap / EV from Yahoo
        "market_cap": target_info.get("market_cap"),
        "enterprise_value": target_info.get("enterprise_value"),
        # TSR vs peer median (percentage points)
        "tsr_1y_vs_peer": _gap(target_tsr_1y, peer_tsr_1y),
        "tsr_3y_vs_peer": _gap(target_tsr_3y, peer_tsr_3y),
        "tsr_5y_vs_peer": _gap(target_tsr_5y, peer_tsr_5y),
        # Multiples vs peer (% discount/premium)
        "ev_ebitda_discount_vs_peer": _multiple_discount(
            target_ev_ebitda, peer_ev_ebitda),
        "pe_discount_vs_peer": _multiple_discount(
            target_pe, peer_pe),
        # Momentum (0-100, higher = better)
        "recent_stock_momentum_score": target_momentum,
        # Insider ownership from Yahoo (best-effort)
        "insider_ownership_pct": (target_info.get("held_pct_insiders") or 0) * 100.0
            if target_info.get("held_pct_insiders") else 0.0,
        # Diagnostics for the audit trail
        "_yahoo_diagnostics": {
            "peer_tickers": peer_tickers,
            "peer_tsr_3y_median": peer_tsr_3y,
            "peer_ev_ebitda_median": peer_ev_ebitda,
            "target_tsr_3y": target_tsr_3y,
            "target_ev_ebitda": target_ev_ebitda,
        },
    }


def enrich_data_dict(data, verbose=False):
    """Take the dict returned by EDGAR ingest and enrich the financials
    + companies tables with Yahoo-derived peer-relative metrics.

    Mutates and returns the input dict.
    """
    _require_yfinance()
    companies = data.get("companies")
    financials = data.get("financials")
    if companies is None or len(companies) == 0:
        return data
    if financials is None:
        financials = pd.DataFrame({"company_id": companies["company_id"]})

    # Build a sic lookup for default peer assignment
    sic_lookup = {}
    if "industry" in companies.columns:
        # We stored sicDescription not the numeric SIC in EDGAR ingest;
        # fall back to default peer set (tech) if not derivable
        pass

    enriched_rows = []
    for _, comp in companies.iterrows():
        ticker = str(comp.get("ticker") or comp.get("company_id"))
        try:
            yres = enrich_with_yahoo(ticker, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"    {ticker} enrichment failed: {e}")
            continue

        # update companies row in place
        idx = companies.index[companies["ticker"] == ticker]
        if len(idx):
            for col in ("market_cap", "enterprise_value"):
                if yres.get(col) is not None:
                    companies.loc[idx, col] = yres[col]
            if yres.get("insider_ownership_pct"):
                companies.loc[idx, "insider_ownership_pct"] = \
                    yres["insider_ownership_pct"]

        # build/update financials row
        fin_row = {
            "company_id": ticker,
            "tsr_1y_vs_peer": yres["tsr_1y_vs_peer"],
            "tsr_3y_vs_peer": yres["tsr_3y_vs_peer"],
            "tsr_5y_vs_peer": yres["tsr_5y_vs_peer"],
            "ev_ebitda_discount_vs_peer": yres["ev_ebitda_discount_vs_peer"],
            "pe_discount_vs_peer": yres["pe_discount_vs_peer"],
            "recent_stock_momentum_score": yres["recent_stock_momentum_score"],
        }
        enriched_rows.append(fin_row)

    if enriched_rows:
        new_fin = pd.DataFrame(enriched_rows)
        # merge into existing financials, preserving any fields we didn't compute
        if len(financials) > 0:
            financials = financials.set_index("company_id")
            new_fin = new_fin.set_index("company_id")
            for col in new_fin.columns:
                financials[col] = new_fin[col]
            financials = financials.reset_index()
        else:
            financials = new_fin

    data["companies"] = companies
    data["financials"] = financials
    return data
