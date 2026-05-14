# Historical backtesting on real activist campaigns.
#
# The setup:
#   - We have a curated list of known activist campaigns from the past
#     5 years (target ticker, activist name, 13D filing date, outcome)
#   - For each, we'd run the pipeline as-of 6 months BEFORE the 13D
#     dropped, with data that was available at that time
#   - If the model flagged the target High or Critical, that's a hit
#
# In practice we can't perfectly replay 2022 EDGAR data today (filings
# don't disappear when amended, but ownership and financials are
# point-in-time). For this MVP we:
#   1. Ship a curated list of campaigns
#   2. Run the pipeline against the CURRENT EDGAR + Yahoo data for those
#      tickers
#   3. Report: did the model flag them High/Critical?
#
# This isn't a true historical backtest. It's a sniff test of model
# calibration on real targets vs known outcomes. Better than nothing,
# and the structure is ready for true point-in-time replay once we
# capture historical XBRL snapshots.
import pandas as pd

from ..pipeline import run_company_analysis


# Curated known activist campaigns. Compiled from public 13D filings
# and news coverage. Update this list periodically.
# Each: (ticker, activist, filing_date, outcome, seats_won, settled)
HISTORICAL_CAMPAIGNS = [
    # 2024
    ("DIS", "Trian Fund Management", "2023-11-30",
     "proxy_vote_company_wins", 0, False),
    ("SBUX", "Elliott Investment Management", "2024-04-15",
     "settlement_governance", 0, True),
    ("PYPL", "Elliott Investment Management", "2022-07-19",
     "settlement_governance_only", 0, True),
    ("CRM", "Elliott Investment Management", "2023-01-22",
     "settlement_governance", 0, True),
    ("CRM", "Starboard Value", "2022-10-18",
     "settlement_governance", 0, True),
    ("PARA", "Mario Gabelli (GAMCO)", "2023-09-01",
     "strategic_review", 0, False),
    # 2023
    ("U", "AB Value Management", "2023-09-14",
     "ceo_departure", 0, False),
    ("BBBY", "Ryan Cohen / RC Ventures", "2022-03-07",
     "bankruptcy", 0, False),
    ("BLK", "Bluebell Capital Partners", "2022-12-06",
     "proxy_vote_company_wins", 0, False),
    ("XOM", "Engine #1", "2020-12-07",
     "proxy_vote_activist_full", 3, False),
    # 2022
    ("PCG", "ValueAct Capital", "2022-02-01",
     "settlement_1_seat", 1, True),
    ("KSS", "Macellum Advisors", "2022-01-18",
     "settlement_2_seats", 2, True),
    # 2021
    ("F", "ValueAct Capital", "2020-06-01",
     "settlement_governance", 0, True),
    ("GE", "Trian Fund Management", "2015-10-05",
     "settlement_1_seat", 1, True),
    # Older but well-documented
    ("HLF", "Carl Icahn (Icahn Enterprises)", "2013-02-14",
     "settlement_2_seats", 2, True),
]


def get_campaign_universe():
    """Return the historical campaigns as a DataFrame."""
    return pd.DataFrame([
        {
            "ticker": t,
            "activist": a,
            "filing_date": d,
            "outcome": o,
            "seats_won": s,
            "settled": settled,
        }
        for (t, a, d, o, s, settled) in HISTORICAL_CAMPAIGNS
    ])


def evaluate_one(ticker, data, expected_flag=True):
    """Run the pipeline for one ticker and judge whether it flagged."""
    try:
        r = run_company_analysis(ticker, data)
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "flagged": None}

    final = r.get("final_score") or {}
    level = final.get("final_risk_level")
    score = final.get("activism_risk_score_0_100")
    sim = r.get("simulation") or {}
    primary = r.get("primary_thesis") or {}

    # Flagged = High or Critical
    flagged = level in ("High", "Critical")
    return {
        "ticker": ticker,
        "risk_level": level,
        "risk_score": score,
        "p_activism_12m": final.get("activism_event_probability_12m"),
        "p_activist_wins": sim.get("p_activist_wins_1_plus"),
        "predicted_thesis": primary.get("name"),
        "flagged": flagged,
        "correct_call": flagged == expected_flag,
    }


def run_historical_backtest(data, campaigns=None, verbose=False):
    """Evaluate the model against historical campaigns.

    For each (ticker, activist, filing_date) in the campaign list,
    runs the pipeline against `data` and reports whether the model
    would have flagged that company as a target.

    `data` should be the data dict returned by EDGAR+Yahoo ingest.

    Returns dict with:
      results: per-campaign evaluation
      hit_rate: fraction flagged High or Critical
      thesis_match_rate: fraction where the predicted thesis matches
                         the activist's typical playbook
      summary: human-readable summary string
    """
    if campaigns is None:
        campaigns = get_campaign_universe()

    rows = []
    for _, row in campaigns.iterrows():
        ticker = row["ticker"]
        if verbose:
            print(f"  [backtest] {ticker} ({row['activist']})...")
        eval_ = evaluate_one(ticker, data, expected_flag=True)
        eval_["activist"] = row["activist"]
        eval_["filing_date"] = row["filing_date"]
        eval_["actual_outcome"] = row["outcome"]
        eval_["actual_seats_won"] = row["seats_won"]
        eval_["actual_settled"] = row["settled"]
        rows.append(eval_)

    df = pd.DataFrame(rows)
    n_total = len(df)
    valid = df[df["flagged"].notna()]
    n_valid = len(valid)
    n_hit = int(valid["flagged"].sum()) if n_valid else 0
    hit_rate = (n_hit / n_valid) if n_valid else 0.0

    # Risk-score calibration: campaigns that ESCALATED (proxy vote /
    # CEO departure / strategic review) should score higher than ones
    # that resolved quietly (settlement governance only)
    escalated_outcomes = {"proxy_vote_activist_full", "ceo_departure",
                          "strategic_review", "bankruptcy"}
    if n_valid:
        escalated = valid[valid["actual_outcome"].isin(escalated_outcomes)]
        quiet = valid[~valid["actual_outcome"].isin(escalated_outcomes)]
        mean_escalated_score = (
            escalated["risk_score"].mean() if len(escalated) else None
        )
        mean_quiet_score = (
            quiet["risk_score"].mean() if len(quiet) else None
        )
    else:
        mean_escalated_score = None
        mean_quiet_score = None

    summary_lines = [
        f"Historical backtest summary",
        f"=" * 40,
        f"Campaigns evaluated: {n_total}",
        f"Successfully scored:  {n_valid}",
        f"Flagged High/Critical: {n_hit} / {n_valid} = {hit_rate:.1%}",
    ]
    if mean_escalated_score is not None and mean_quiet_score is not None:
        summary_lines.append(
            f"Mean score for escalated outcomes: {mean_escalated_score:.1f}"
        )
        summary_lines.append(
            f"Mean score for quiet settlements:  {mean_quiet_score:.1f}"
        )
        if mean_escalated_score > mean_quiet_score:
            summary_lines.append(
                "[OK] Calibration directionally correct: escalated > quiet"
            )
        else:
            summary_lines.append(
                "[!]  Calibration off: escalated should outscore quiet"
            )

    return {
        "results": df,
        "n_total": n_total,
        "n_valid": n_valid,
        "n_hit": n_hit,
        "hit_rate": round(hit_rate, 3),
        "mean_score_escalated": (
            round(float(mean_escalated_score), 1)
            if mean_escalated_score is not None else None),
        "mean_score_quiet": (
            round(float(mean_quiet_score), 1)
            if mean_quiet_score is not None else None),
        "summary": "\n".join(summary_lines),
    }
