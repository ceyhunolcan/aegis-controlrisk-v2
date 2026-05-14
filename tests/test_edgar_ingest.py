# Tests for the EDGAR ingest. We mock requests.get so tests don't hit
# the actual SEC API - they run in CI offline and are fast.
import json
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


# --- mock fixtures ---------------------------------------------------------

MOCK_TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}

MOCK_SUBMISSIONS = {
    "cik": "0000320193",
    "name": "APPLE INC",
    "sic": "3571",
    "sicDescription": "Electronic Computers",
    "fiscalYearEnd": "09-30",
    "exchanges": ["Nasdaq"],
    "addresses": {"business": {"country": "United States"}},
    "filings": {
        "recent": {
            "accessionNumber": ["0000320193-26-000001",
                                "0000320193-26-000002",
                                "0000320193-26-000003"],
            "form": ["10-K", "8-K", "8-K"],
            "filingDate": ["2026-01-15", "2026-02-01", "2026-03-15"],
            "reportDate": ["2025-12-31", "", ""],
            "primaryDocument": ["aapl-10k.htm", "aapl-8k.htm", "aapl-8k.htm"],
            "items": ["", "2.02,7.01", "5.02"],
        }
    },
}


def _mock_get(url, *args, **kwargs):
    """Pretend to be requests.get. Return what EDGAR would return."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    if "company_tickers.json" in url:
        resp.json.return_value = MOCK_TICKERS
    elif "/submissions/CIK" in url:
        resp.json.return_value = MOCK_SUBMISSIONS
    elif "/companyconcept/" in url:
        resp.json.return_value = {
            "cik": 320193,
            "taxonomy": "us-gaap",
            "tag": "Revenues",
            "units": {"USD": [
                {"end": "2025-12-31", "val": 400_000_000_000, "fy": 2025,
                 "fp": "FY", "form": "10-K"},
            ]},
        }
    else:
        resp.status_code = 404
        resp.raise_for_status.side_effect = Exception("404")
    return resp


# --- core tests ------------------------------------------------------------

def test_edgar_client_throttles(tmp_path):
    """Two back-to-back requests must respect the rate limit."""
    from aegis.ingest.edgar import EDGARClient
    import time

    # Mock get returns a generic 200 for any URL
    def _generic_ok(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"ok": True}
        return resp

    client = EDGARClient(cache_dir=tmp_path, rate_limit_sec=0.1)
    with patch("aegis.ingest.edgar.requests.get", side_effect=_generic_ok):
        t0 = time.time()
        client.get_json("https://example.com/a.json", max_age_sec=0)
        client.get_json("https://example.com/b.json", max_age_sec=0)
        elapsed = time.time() - t0
    # at least one rate-limit delay between two distinct cache misses
    assert elapsed >= 0.1


def test_edgar_client_caches(tmp_path):
    """Second identical request should be served from disk, not http."""
    from aegis.ingest.edgar import EDGARClient

    def _generic_ok(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"ok": True}
        return resp

    client = EDGARClient(cache_dir=tmp_path)
    with patch("aegis.ingest.edgar.requests.get",
               side_effect=_generic_ok) as m:
        client.get_json("https://example.com/cached.json")
        client.get_json("https://example.com/cached.json")
    assert m.call_count == 1


def test_ticker_to_cik_resolves(tmp_path):
    """Look up a known ticker and get back a zero-padded CIK."""
    from aegis.ingest.edgar import EDGARClient, ticker_to_cik
    import aegis.ingest.edgar as edgar_mod

    # Clear the module-level ticker cache so we hit our mock
    edgar_mod._TICKERS_CACHE = {}

    client = EDGARClient(cache_dir=tmp_path)
    with patch("aegis.ingest.edgar.requests.get", side_effect=_mock_get):
        cik, name = ticker_to_cik("AAPL", client=client)
    assert cik == "0000320193"
    assert "APPLE" in name.upper()


def test_ticker_to_cik_unknown_raises(tmp_path):
    from aegis.ingest.edgar import EDGARClient, ticker_to_cik
    import aegis.ingest.edgar as edgar_mod
    edgar_mod._TICKERS_CACHE = {}

    client = EDGARClient(cache_dir=tmp_path)
    with patch("aegis.ingest.edgar.requests.get", side_effect=_mock_get):
        with pytest.raises(KeyError):
            ticker_to_cik("DOESNOTEXIST", client=client)


def test_list_filings_filters_by_form(tmp_path):
    from aegis.ingest.edgar import EDGARClient, list_filings
    import aegis.ingest.edgar as edgar_mod
    edgar_mod._TICKERS_CACHE = {}

    client = EDGARClient(cache_dir=tmp_path)
    with patch("aegis.ingest.edgar.requests.get", side_effect=_mock_get):
        df = list_filings("AAPL", form_types=["8-K"], client=client)
    assert len(df) == 2  # the mock has 2 8-K filings
    assert all(df["form"] == "8-K")


def test_classify_8k_items_handles_known_codes():
    """The 8-K item classifier should map known codes to event types."""
    from aegis.ingest.edgar import _classify_8k_items

    # 5.02 = officer/director change
    etype, sev, desc = _classify_8k_items("5.02")
    assert etype == "officer_director_change"
    assert sev > 0
    assert "officer" in desc.lower() or "director" in desc.lower()

    # 4.02 = restatement; should be more severe than 2.02 earnings
    e1, sev1, _ = _classify_8k_items("4.02")
    e2, sev2, _ = _classify_8k_items("2.02")
    assert sev1 > sev2

    # Empty input -> nothing
    assert _classify_8k_items("") == (None, None, None)
    assert _classify_8k_items(None) == (None, None, None)


def test_classify_8k_items_picks_most_severe():
    """When multiple items appear, the classifier returns the most severe."""
    from aegis.ingest.edgar import _classify_8k_items
    # 2.02 (earnings, sev 35) + 4.02 (restatement, sev 85)
    etype, sev, _ = _classify_8k_items("2.02,4.02")
    assert etype == "restatement"
    assert sev == 85


def test_sic_to_sector():
    from aegis.ingest.edgar import _sic_to_sector
    assert _sic_to_sector("3571") == "Manufacturing"
    assert _sic_to_sector("6021") == "Financials"
    assert _sic_to_sector("9999") == "Unknown"
    assert _sic_to_sector("not-a-number") == "Unknown"
    assert _sic_to_sector(None) == "Unknown"


def test_edgar_source_load_for_tickers_smoke(tmp_path):
    """End-to-end: load_for_tickers returns the full data dict shape."""
    from aegis.ingest.edgar import EDGARSource
    import aegis.ingest.edgar as edgar_mod
    edgar_mod._TICKERS_CACHE = {}

    src = EDGARSource(cache_dir=tmp_path)
    with patch("aegis.ingest.edgar.requests.get", side_effect=_mock_get):
        data = src.load_for_tickers(["AAPL"])

    # All expected keys present
    assert set(data.keys()) >= {
        "companies", "financials", "directors", "ownership",
        "shareholders", "events", "campaigns",
        "activist_archetypes", "proxy_advisor_cases",
    }
    # Companies populated for AAPL
    assert len(data["companies"]) == 1
    assert data["companies"].iloc[0]["ticker"] == "AAPL"
    # Events extracted from the 2 mock 8-Ks
    assert len(data["events"]) >= 1
    # Empty tables we left to vendor data
    assert len(data["campaigns"]) == 0


def test_fetch_tickers_writes_csvs(tmp_path):
    """fetch_tickers should write all 9 expected CSVs to disk."""
    from aegis.ingest.edgar import fetch_tickers
    import aegis.ingest.edgar as edgar_mod
    edgar_mod._TICKERS_CACHE = {}

    output_dir = tmp_path / "out"
    with patch("aegis.ingest.edgar.requests.get", side_effect=_mock_get):
        fetch_tickers(["AAPL"], user_agent="Test test@example.com",
                      output_dir=output_dir)

    expected = {
        "sample_companies.csv", "sample_financials.csv",
        "sample_directors.csv", "sample_ownership.csv",
        "sample_shareholders.csv", "sample_events.csv",
        "sample_campaigns.csv", "sample_activist_archetypes.csv",
        "sample_proxy_advisor_cases.csv",
    }
    written = {p.name for p in output_dir.iterdir()}
    missing = expected - written
    assert not missing, f"missing CSVs: {missing}"


def test_loader_accepts_edgar_output(tmp_path):
    """After EDGAR fetch, the standard loader should ingest those CSVs
    without crashing or regenerating synthetic data."""
    from aegis.ingest.edgar import fetch_tickers
    from aegis.data.loader import load_all_data
    import aegis.ingest.edgar as edgar_mod
    edgar_mod._TICKERS_CACHE = {}

    output_dir = tmp_path / "out"
    with patch("aegis.ingest.edgar.requests.get", side_effect=_mock_get):
        fetch_tickers(["AAPL"], user_agent="Test test@example.com",
                      output_dir=output_dir)

    data = load_all_data(str(output_dir))
    assert "companies" in data
    assert len(data["companies"]) == 1
    assert data["companies"].iloc[0]["ticker"] == "AAPL"
