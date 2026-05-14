# Loads the sample CSVs, generates them on first run if they're missing,
# and does a bit of dtype hygiene because pandas will helpfully turn a
# "True" string into something that breaks downstream comparisons later.
from pathlib import Path
import pandas as pd
import numpy as np

from . import synthetic_data


_BOOL_COLS = {
    "controlled_company_flag", "dual_class_flag", "has_poison_pill",
    "classified_board", "ceo_chair_combined", "majority_voting_standard",
    "independent", "is_committee_chair", "compensation_oversight_flag",
    "audit_oversight_flag", "governance_oversight_flag",
    "settled", "went_to_vote",
}
_ID_COLS = {
    "company_id", "ticker", "director_id", "holder_id", "campaign_id",
    "archetype_id", "case_id", "event_id",
}
_DATE_COLS = {
    "annual_meeting_date", "nomination_deadline", "campaign_start_date",
    "event_date",
}


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    if isinstance(v, (int, np.integer)) or isinstance(v, float):
        try:
            return bool(int(v))
        except Exception:
            return False
    s = str(v).strip().lower()
    return s in {"true", "t", "yes", "y", "1"}


def _coerce_bool_series(s):
    return s.map(_to_bool).astype(bool)


def _ensure_csvs(data_dir):
    needed = [
        "sample_companies.csv", "sample_financials.csv", "sample_directors.csv",
        "sample_shareholders.csv", "sample_ownership.csv", "sample_campaigns.csv",
        "sample_activist_archetypes.csv", "sample_proxy_advisor_cases.csv",
        "sample_events.csv",
    ]
    missing = [f for f in needed if not (data_dir / f).exists()]
    if missing:
        synthetic_data.generate_all(str(data_dir))


def _load_one(path):
    df = pd.read_csv(path)
    for col in df.columns:
        if col in _BOOL_COLS:
            df[col] = _coerce_bool_series(df[col])
        elif col in _ID_COLS or col in _DATE_COLS:
            df[col] = df[col].astype(str)
        else:
            # Best-effort numeric coercion - only commit if most values parse
            if df[col].dtype == "object":
                converted = pd.to_numeric(df[col], errors="coerce")
                if converted.notna().sum() >= max(1, int(0.5 * len(df))):
                    df[col] = converted
    return df


def _fill_neutral(df, defaults):
    for col, val in defaults.items():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(val)
    return df


def load_all_data(data_dir="data"):
    """Returns dict with one DataFrame per table. Generates CSVs on first run."""
    dp = Path(data_dir)
    dp.mkdir(parents=True, exist_ok=True)
    _ensure_csvs(dp)

    out = {
        "companies":           _load_one(dp / "sample_companies.csv"),
        "financials":          _load_one(dp / "sample_financials.csv"),
        "directors":           _load_one(dp / "sample_directors.csv"),
        "shareholders":        _load_one(dp / "sample_shareholders.csv"),
        "ownership":           _load_one(dp / "sample_ownership.csv"),
        "campaigns":           _load_one(dp / "sample_campaigns.csv"),
        "activist_archetypes": _load_one(dp / "sample_activist_archetypes.csv"),
        "proxy_advisor_cases": _load_one(dp / "sample_proxy_advisor_cases.csv"),
        "events":              _load_one(dp / "sample_events.csv"),
    }

    # Financials: neutral defaults so downstream math doesn't blow up on NaN
    out["financials"] = _fill_neutral(out["financials"], {
        "tsr_1y_vs_peer": 0.0, "tsr_3y_vs_peer": 0.0, "tsr_5y_vs_peer": 0.0,
        "ev_ebitda_discount_vs_peer": 0.0, "pe_discount_vs_peer": 0.0,
        "roic_gap_vs_peer": 0.0, "ebitda_margin_gap_vs_peer": 0.0,
        "fcf_yield_vs_peer": 0.0, "capex_intensity_vs_peer": 0.0,
        "revenue_growth_vs_peer": 0.0, "leverage_vs_peer": 0.0,
        "guidance_miss_frequency": 0.2, "earnings_miss_frequency": 0.2,
        "mna_writeoff_history_score": 50.0, "say_on_pay_support_pct": 90.0,
        "director_vote_support_avg_pct": 95.0,
        "recent_stock_momentum_score": 50.0,
    })

    out["companies"] = _fill_neutral(out["companies"], {
        "insider_ownership_pct": 0.0, "market_cap": 0.0, "enterprise_value": 0.0,
    })

    out["directors"] = _fill_neutral(out["directors"], {
        "age": 60, "tenure_years": 5.0, "other_public_boards": 0,
        "prior_vote_support_pct": 95.0, "sector_expertise_score": 50.0,
        "capital_allocation_expertise_score": 50.0,
        "technology_expertise_score": 50.0,
        "climate_transition_expertise_score": 50.0,
    })

    # NaN in string fields (committee_roles, name) leaks into outputs as float('nan')
    # which then JSON-serializes weirdly. Force these to strings.
    for col in ("committee_roles", "name"):
        if col in out["directors"].columns:
            out["directors"][col] = (
                out["directors"][col].fillna("").astype(str)
                .replace({"nan": "", "None": ""})
            )

    out["shareholders"] = _fill_neutral(out["shareholders"], {
        "governance_sensitivity_score": 50.0, "activism_support_history_score": 50.0,
        "proxy_advisor_dependence_score": 50.0, "esg_sensitivity_score": 50.0,
        "value_orientation_score": 50.0, "settlement_preference_score": 50.0,
        "retail_mobilization_score": 30.0,
    })

    out["ownership"] = _fill_neutral(out["ownership"], {
        "ownership_pct": 0.0, "qoq_change_pct": 0.0, "voting_power_pct": 0.0,
    })

    out["events"] = _fill_neutral(out["events"], {"severity_score": 50.0})

    return out
