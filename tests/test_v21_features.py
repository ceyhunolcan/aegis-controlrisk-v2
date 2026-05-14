# Tests for the v2.1 additions: yahoo ingest, activist archetypes,
# universe scanner, historical backtest.
import pandas as pd
import pytest


# --- Activist archetypes ---------------------------------------------------

def test_activist_archetypes_df_shape():
    from aegis.ingest.activists import build_archetypes_df
    df = build_archetypes_df()
    assert len(df) >= 15  # we ship at least 15 real + 3 generic
    expected_cols = {"archetype_id", "name", "aum_usd",
                     "typical_stake_pct", "typical_seats_requested",
                     "preferred_market_cap_min", "preferred_market_cap_max",
                     "preferred_thesis_types", "campaign_style"}
    assert expected_cols.issubset(set(df.columns))


def test_activist_archetypes_have_real_funds():
    """Verify the archetypes include the actual major activists."""
    from aegis.ingest.activists import build_archetypes_df
    df = build_archetypes_df()
    names = set(df["name"].str.lower())
    # These are well-known real activists. If they're missing, the
    # archetype DB has been broken.
    for fund in ["elliott", "trian", "starboard", "valueact", "jana"]:
        assert any(fund in n for n in names), f"missing {fund}"


def test_find_archetype_known_id():
    from aegis.ingest.activists import find_archetype
    a = find_archetype("ACT_ELLIOTT")
    assert a is not None
    assert "elliott" in a["name"].lower()
    assert a["aum_usd"] > 1e10  # Elliott is a multi-billion shop


def test_find_archetype_unknown_id_returns_none():
    from aegis.ingest.activists import find_archetype
    assert find_archetype("ACT_DOES_NOT_EXIST") is None


# --- Universe scanner -----------------------------------------------------

def test_scan_universe_ranks_descending():
    from aegis.data.loader import load_all_data
    from aegis.scanning import scan_universe

    data = load_all_data("data")
    df = scan_universe(data)
    assert len(df) > 0
    # First row should have the highest risk_score
    scores = df["risk_score"].dropna().tolist()
    assert scores == sorted(scores, reverse=True), \
        "scan results should be sorted by risk_score desc"


def test_scan_universe_top_n_limits():
    from aegis.data.loader import load_all_data
    from aegis.scanning import scan_universe

    data = load_all_data("data")
    df = scan_universe(data, top_n=3)
    assert len(df) <= 3


def test_scan_alerts_filter():
    from aegis.data.loader import load_all_data
    from aegis.scanning import scan_universe, scan_alerts

    data = load_all_data("data")
    df = scan_universe(data)
    high_plus = scan_alerts(df, risk_level_min="High")
    # Everything in high_plus should be High or Critical
    for level in high_plus["risk_level"]:
        assert level in ("High", "Critical")


def test_format_scan_report_text():
    from aegis.data.loader import load_all_data
    from aegis.scanning import scan_universe, format_scan_report

    data = load_all_data("data")
    df = scan_universe(data, top_n=3)
    text = format_scan_report(df, format_="text")
    assert "company_id" in text
    assert "risk_level" in text


def test_format_scan_report_markdown():
    from aegis.data.loader import load_all_data
    from aegis.scanning import scan_universe, format_scan_report

    data = load_all_data("data")
    df = scan_universe(data, top_n=3)
    md = format_scan_report(df, format_="markdown")
    # Markdown tables have pipe characters as column separators
    assert "|" in md


def test_heatmap_by_sector():
    from aegis.data.loader import load_all_data
    from aegis.scanning import scan_universe, heatmap_by_sector

    data = load_all_data("data")
    df = scan_universe(data)
    h = heatmap_by_sector(df)
    assert len(h) > 0
    assert "sector" in h.columns
    assert "n_companies" in h.columns
    # n_critical should never exceed n_companies for any sector
    for _, row in h.iterrows():
        assert row["n_critical"] <= row["n_companies"]


# --- Historical backtest --------------------------------------------------

def test_get_campaign_universe_has_known_campaigns():
    from aegis.backtesting.historical import get_campaign_universe
    df = get_campaign_universe()
    assert len(df) >= 10
    # Engine #1's ExxonMobil campaign is the most-cited; should be in.
    xom = df[df["ticker"] == "XOM"]
    assert len(xom) >= 1
    # Trian/Disney is in there
    dis = df[df["ticker"] == "DIS"]
    assert len(dis) >= 1


def test_evaluate_one_returns_expected_keys():
    from aegis.data.loader import load_all_data
    from aegis.backtesting.historical import evaluate_one

    data = load_all_data("data")
    # Use a synthetic ticker since we don't have real EDGAR data here.
    # The synthetic INDC is a Critical-rated underperformer.
    result = evaluate_one("INDC", data, expected_flag=True)
    for key in ("ticker", "risk_level", "risk_score", "flagged"):
        assert key in result


def test_run_historical_backtest_returns_summary():
    """Smoke test: backtest doesn't crash even on a tiny subset."""
    from aegis.data.loader import load_all_data
    from aegis.backtesting.historical import run_historical_backtest
    import pandas as pd

    data = load_all_data("data")
    # Force a tiny universe so the test runs fast and doesn't need
    # all tickers to be present in the synthetic data
    campaigns = pd.DataFrame([
        {"ticker": "INDC", "activist": "Test Activist",
         "filing_date": "2024-01-01", "outcome": "settlement_governance",
         "seats_won": 0, "settled": True},
    ])
    result = run_historical_backtest(data, campaigns=campaigns)
    assert "results" in result
    assert "hit_rate" in result
    assert "summary" in result
    assert isinstance(result["hit_rate"], float)


# --- Yahoo ingest (mocked - we don't hit Yahoo in CI) ---------------------

def test_yahoo_import_optional():
    """yahoo module should import even without yfinance installed."""
    from aegis.ingest import yahoo  # noqa
    # _HAS_YFINANCE may be False; that's fine


def test_compute_tsr_handles_empty():
    from aegis.ingest.yahoo import compute_tsr
    assert compute_tsr(None, 1) is None
    import pandas as pd
    assert compute_tsr(pd.DataFrame(), 1) is None


def test_compute_tsr_known_values():
    """Build a synthetic price series and verify TSR math."""
    from aegis.ingest.yahoo import compute_tsr
    import pandas as pd
    import numpy as np

    dates = pd.date_range("2020-01-01", "2025-01-01", freq="D")
    # Linear price doubling over 5 years
    prices = np.linspace(100, 200, len(dates))
    df = pd.DataFrame({"date": dates, "close": prices, "volume": 1000})

    # 5y TSR should be approximately 100%
    tsr = compute_tsr(df, 5)
    assert tsr is not None
    assert 95 <= tsr <= 105


def test_compute_momentum_score_bounded():
    """Momentum score is always 0-100 regardless of input."""
    from aegis.ingest.yahoo import compute_momentum_score
    import pandas as pd
    import numpy as np

    # extreme price crash
    dates = pd.date_range("2020-01-01", periods=400, freq="D")
    crash = np.linspace(100, 1, len(dates))
    df = pd.DataFrame({"date": dates, "close": crash, "volume": 1000})
    score = compute_momentum_score(df)
    assert 0 <= score <= 100

    # extreme price rip
    rip = np.linspace(1, 100, len(dates))
    df["close"] = rip
    score = compute_momentum_score(df)
    assert 0 <= score <= 100


def test_peers_for_sic():
    from aegis.ingest.yahoo import _peers_for_sic
    fin_peers = _peers_for_sic("6021")  # bank
    assert "JPM" in fin_peers or "BAC" in fin_peers
    tech_peers = _peers_for_sic("7372")  # software
    # falls back to tech default
    assert len(tech_peers) > 0
    # bad input still returns a list
    assert isinstance(_peers_for_sic(None), list)
    assert isinstance(_peers_for_sic("xyz"), list)
