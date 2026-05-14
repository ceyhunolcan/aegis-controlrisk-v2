# Universe scanner. Run the pipeline against a list of companies and
# rank them by activism vulnerability. The output is the table a banker
# would want to see in their Monday morning briefing: "who's most at
# risk this week, sorted descending."
#
# This is structurally different from `aegis_cli.py analyze` which is
# per-company. Scanner is bulk + ranked + actionable.
import pandas as pd

from ..pipeline import run_company_analysis


def scan_universe(data, as_of_date=None, top_n=None):
    """Run the pipeline across every company in the data dict, return a
    ranked DataFrame of vulnerability summaries.

    Returns columns:
        company_id, name, sector, risk_level, risk_score,
        p_activism_12m, p_activist_wins, primary_thesis,
        days_to_meeting, days_to_nomination_deadline, n_active_triggers,
        vulnerability_score, defense_score, settlement_path
    """
    companies = data.get("companies")
    if companies is None or len(companies) == 0:
        return pd.DataFrame()

    rows = []
    for cid in companies["company_id"].astype(str).tolist():
        try:
            r = run_company_analysis(cid, data, as_of_date=as_of_date)
        except Exception as e:
            rows.append({
                "company_id": cid,
                "name": cid,
                "error": str(e),
                "risk_score": None,
            })
            continue

        company = r.get("company") or {}
        final = r.get("final_score") or {}
        sim = r.get("simulation") or {}
        vuln = r.get("vulnerability") or {}
        defense = r.get("defense") or {}
        primary = r.get("primary_thesis") or {}
        legal = r.get("legal") or {}
        triggers = r.get("triggers") or {}
        settlement = r.get("settlement") or {}

        rows.append({
            "company_id": cid,
            "name": company.get("name", cid),
            "sector": company.get("sector", "—"),
            "risk_level": final.get("final_risk_level"),
            "risk_score": final.get("activism_risk_score_0_100"),
            "p_activism_12m": final.get("activism_event_probability_12m"),
            "p_activist_wins": sim.get("p_activist_wins_1_plus"),
            "primary_thesis": primary.get("name"),
            "thesis_score": primary.get("score"),
            "days_to_meeting": legal.get("days_to_annual_meeting"),
            "days_to_nomination_deadline":
                legal.get("days_to_nomination_deadline"),
            "n_active_triggers": triggers.get("n_triggers", 0),
            "vulnerability_score": vuln.get("score"),
            "defense_score": defense.get("defense_strength_score"),
            "settlement_path": settlement.get("recommended_path"),
        })

    df = pd.DataFrame(rows)
    if "risk_score" in df.columns:
        df = df.sort_values("risk_score", ascending=False,
                            na_position="last").reset_index(drop=True)
    if top_n:
        df = df.head(top_n)
    return df


def format_scan_report(scan_df, format_="text"):
    """Pretty-print a scan result.

    format_: 'text' (terminal), 'markdown' (for docs), 'csv' (for files)
    """
    if scan_df is None or len(scan_df) == 0:
        return "(no companies scanned)"

    if format_ == "csv":
        return scan_df.to_csv(index=False)

    # subset of columns for display
    display = scan_df[["company_id", "name", "sector", "risk_level",
                       "risk_score", "p_activism_12m",
                       "primary_thesis", "days_to_nomination_deadline",
                       "n_active_triggers"]].copy()
    # Tidy numeric formatting
    if "risk_score" in display.columns:
        display["risk_score"] = display["risk_score"].apply(
            lambda v: f"{float(v):.0f}" if v is not None
            and not pd.isna(v) else "—")
    if "p_activism_12m" in display.columns:
        display["p_activism_12m"] = display["p_activism_12m"].apply(
            lambda v: f"{float(v)*100:.0f}%" if v is not None
            and not pd.isna(v) else "—")

    if format_ == "markdown":
        return display.to_markdown(index=False)
    # default: terminal-friendly text
    return display.to_string(index=False)


def scan_alerts(scan_df, risk_level_min="High"):
    """Return only companies at or above a risk-level threshold."""
    order = {"Low": 0, "Moderate": 1, "High": 2, "Critical": 3}
    threshold = order.get(risk_level_min, 2)
    return scan_df[
        scan_df["risk_level"].map(lambda r: order.get(r, -1)) >= threshold
    ].reset_index(drop=True)


def heatmap_by_sector(scan_df):
    """Aggregate the scan into a sector-level heatmap.

    Returns a DataFrame with one row per sector, columns:
    sector, n_companies, n_critical, n_high, mean_score, max_score
    """
    if scan_df is None or len(scan_df) == 0:
        return pd.DataFrame()

    def _count(group, level):
        return int((group["risk_level"] == level).sum())

    g = scan_df.groupby("sector", dropna=False)
    out = g.apply(lambda x: pd.Series({
        "n_companies": len(x),
        "n_critical": _count(x, "Critical"),
        "n_high": _count(x, "High"),
        "n_moderate": _count(x, "Moderate"),
        "n_low": _count(x, "Low"),
        "mean_score": round(float(x["risk_score"].mean()), 1)
                      if x["risk_score"].notna().any() else None,
        "max_score": round(float(x["risk_score"].max()), 1)
                     if x["risk_score"].notna().any() else None,
    })).reset_index()
    return out.sort_values("mean_score", ascending=False,
                           na_position="last").reset_index(drop=True)
