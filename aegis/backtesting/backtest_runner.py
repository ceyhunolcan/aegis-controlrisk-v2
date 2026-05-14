# Run CASCADE-2 over the whole synthetic universe and score it against
# the historical campaign labels. Caveat: with only ~7 companies the metrics
# are more of a wiring sanity check than a real generalisation test, but the
# numbers do swing meaningfully when you break a scoring engine, which is
# what we want from a regression signal.
from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis
from aegis.backtesting.metrics import (
    precision_at_k, recall_at_k, average_rank_of_truth,
    simple_auc_proxy, calibration_bins,
)


def _ground_truth_from_campaigns(campaigns_df):
    """
    company_id -> {had_campaign, any_seats_won, any_settled, n_campaigns,
    predominant_thesis}
    """
    out = {}
    if campaigns_df is None or len(campaigns_df) == 0:
        return out
    for cid, sub in campaigns_df.groupby("company_id"):
        seats = sub["board_seats_won"].astype(float).fillna(0).sum()
        settled_any = sub["settled"].astype(str).str.lower().eq("true").any()
        thesis_counts = sub["thesis_type"].value_counts()
        predominant = thesis_counts.index[0] if len(thesis_counts) else "Unknown"
        out[cid] = {
            "had_campaign": True,
            "any_seats_won": bool(seats > 0),
            "any_settled": bool(settled_any),
            "n_campaigns": int(len(sub)),
            "predominant_thesis": predominant,
        }
    return out


# token-level loose match between predicted and ground-truth thesis labels
_JUNK_TOKENS = {"and", "or", "the", "a", "an", "of", "in", "to", "for", "with"}


def _tokens(s):
    s = (s or "").lower()
    for c in [",", ".", "/", "-", "(", ")", "&"]:
        s = s.replace(c, " ")
    return [t for t in s.split() if t and t not in _JUNK_TOKENS]


def _thesis_match(pred, truth):
    if not pred or not truth:
        return False
    pt = set(_tokens(pred))
    tt = set(_tokens(truth))
    return bool(pt and tt and (pt & tt))


def run_synthetic_backtest(data=None):
    if data is None:
        data = load_all_data("data")

    companies_df = data.get("companies")
    campaigns_df = data.get("campaigns")
    if companies_df is None or len(companies_df) == 0:
        return {"error": "No companies in data"}

    truth = _ground_truth_from_campaigns(campaigns_df)

    per_company = []
    for cid in companies_df["company_id"].astype(str).tolist():
        try:
            r = run_company_analysis(cid, data)
            company = r.get("company") or {}
            final   = r.get("final_score") or {}
            vuln    = r.get("vulnerability") or {}
            sim     = r.get("simulation") or {}
            primary = r.get("primary_thesis") or {}
            t = truth.get(cid, {})
            per_company.append({
                "company_id": cid,
                "name": company.get("name", cid),
                "ticker": company.get("ticker", "—"),
                "vulnerability":     float(vuln.get("score", 0) or 0),
                "final_risk_score":  float(final.get("activism_risk_score_0_100", 0) or 0),
                "p_event_12m":       float(final.get("activism_event_probability_12m", 0) or 0),
                "p_activist_wins_1_plus": float(sim.get("p_activist_wins_1_plus", 0) or 0),
                "primary_thesis": primary.get("name", "—"),
                "ground_truth_had_campaign":         bool(t.get("had_campaign", False)),
                "ground_truth_any_seats_won":        bool(t.get("any_seats_won", False)),
                "ground_truth_predominant_thesis":   t.get("predominant_thesis", ""),
            })
        except Exception as e:
            per_company.append({"company_id": cid, "error": str(e)})

    ranked = sorted(
        [c for c in per_company if "error" not in c],
        key=lambda x: -x["final_risk_score"],
    )
    ranked_ids = [c["company_id"] for c in ranked]
    truth_ids = [cid for cid, t in truth.items() if t.get("had_campaign")]
    n = len(ranked_ids)
    decile_k = max(1, round(n / 10))

    metrics = {
        "precision_at_3":   round(precision_at_k(ranked_ids, truth_ids, 3), 3),
        "precision_at_5":   round(precision_at_k(ranked_ids, truth_ids, 5), 3),
        "recall_at_3":      round(recall_at_k(ranked_ids, truth_ids, 3), 3),
        "recall_at_5":      round(recall_at_k(ranked_ids, truth_ids, 5), 3),
        "recall_top_decile": round(recall_at_k(ranked_ids, truth_ids, decile_k), 3),
        "average_rank_of_truth_companies":
            round(average_rank_of_truth(ranked_ids, truth_ids), 2),
        "n_companies": n,
        "n_truth_companies": len(truth_ids),
    }

    # thesis match
    matched = total = 0
    for c in per_company:
        gt = c.get("ground_truth_predominant_thesis", "")
        if gt:
            total += 1
            if _thesis_match(c.get("primary_thesis", ""), gt):
                matched += 1
    metrics["thesis_match_rate"] = round(matched / total, 3) if total else None

    scores = [c.get("p_event_12m", 0.0) for c in per_company if "error" not in c]
    labels = [1 if c.get("ground_truth_had_campaign") else 0
              for c in per_company if "error" not in c]
    metrics["auc_proxy_event_prob_vs_truth"] = round(simple_auc_proxy(scores, labels), 3)
    metrics["calibration_table"] = calibration_bins(scores, labels, n_bins=5)

    return {
        "metrics": metrics,
        "ranked_companies": ranked,
        "ground_truth": truth,
        "n_companies": n,
        "summary": (
            f"Backtest across {n} synthetic companies: "
            f"precision@3={metrics['precision_at_3']}, "
            f"recall@top-decile={metrics['recall_top_decile']}, "
            f"AUC-proxy={metrics['auc_proxy_event_prob_vs_truth']}, "
            f"thesis match rate={metrics['thesis_match_rate']}."
        ),
    }


if __name__ == "__main__":
    res = run_synthetic_backtest()
    print(res.get("summary"))
    for k, v in (res.get("metrics") or {}).items():
        if k == "calibration_table":
            continue
        print(f"  {k}: {v}")
