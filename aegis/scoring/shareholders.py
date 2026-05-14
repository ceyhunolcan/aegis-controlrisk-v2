# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Shareholder coalition modeling. Builds a directed graph of holders + their
# priors, applies thesis-specific adjustments, and aggregates into an
# expected activist / management / abstain vote split.
#
# The priors below are starting points - they're tuned per-holder using
# governance_sensitivity, activism_support_history, etc. They're round
# numbers on purpose - the data is too noisy to justify two decimal places.
from typing import Dict, List
import networkx as nx
from networkx.readwrite import json_graph

from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100, probability_clamp
)


# (p_support_activist, p_support_mgmt, p_abstain). Sum to 1 by construction.
HOLDER_TYPE_PRIORS = {
    "passive":       (0.40, 0.50, 0.10),  # Index funds follow PA recs
    "active":        (0.45, 0.45, 0.10),  # Mixed
    "pension":       (0.50, 0.40, 0.10),  # Often governance-friendly
    "activist":      (0.95, 0.03, 0.02),
    "insider":       (0.03, 0.95, 0.02),
    "retail":        (0.30, 0.45, 0.25),
    "sovereign":     (0.40, 0.50, 0.10),
    "other":         (0.40, 0.45, 0.15),
}


def _normalize_holder_type(t):
    t = (t or "").lower().strip()
    if t in HOLDER_TYPE_PRIORS:
        return t
    return "other"


def estimate_holder_support(
    holder, ownership_row, company,
    vulnerability, primary_thesis):
    """Estimate one holder's expected vote split given features."""
    if hasattr(holder, "model_dump"):
        holder = holder.model_dump()
    if hasattr(company, "model_dump"):
        company = company.model_dump()

    htype = _normalize_holder_type(safe_get(holder, "holder_type", "other"))
    p_a, p_m, p_x = HOLDER_TYPE_PRIORS.get(htype, HOLDER_TYPE_PRIORS["other"])

    # Adjust for governance sensitivity
    gov = safe_float(safe_get(holder, "governance_sensitivity_score", 50), 50)
    # Higher governance sensitivity tilts toward activist when thesis is governance/ESG
    thesis_name = str(safe_get(primary_thesis, "name", "")).lower()
    if "governance" in thesis_name or "compensation" in thesis_name or "climate" in thesis_name:
        tilt = (gov - 50) / 100.0 * 0.20
        p_a = clamp(p_a + tilt, 0, 1)
        p_m = clamp(p_m - tilt, 0, 1)

    # Adjust for activism support history
    ahs = safe_float(safe_get(holder, "activism_support_history_score", 40), 40)
    tilt2 = (ahs - 50) / 100.0 * 0.15
    p_a = clamp(p_a + tilt2, 0, 1)
    p_m = clamp(p_m - tilt2, 0, 1)

    # ESG sensitivity matters for climate theses
    esg = safe_float(safe_get(holder, "esg_sensitivity_score", 50), 50)
    if "climate" in thesis_name or "esg" in thesis_name or "transition" in thesis_name:
        tilt3 = (esg - 50) / 100.0 * 0.15
        p_a = clamp(p_a + tilt3, 0, 1)
        p_m = clamp(p_m - tilt3, 0, 1)

    # If vulnerability is very high (>75), activist case lands more easily
    v_score = safe_float(safe_get(vulnerability, "score", 50), 50)
    if v_score > 65:
        bump = (v_score - 65) / 100.0 * 0.20
        p_a = clamp(p_a + bump, 0, 1)
        p_m = clamp(p_m - bump, 0, 1)

    # Insider/controlled company: management ownership locks down votes
    if bool(safe_get(company, "controlled_company_flag", False)) and htype not in ("activist", "insider"):
        p_a = clamp(p_a - 0.10, 0, 1)
        p_m = clamp(p_m + 0.10, 0, 1)

    # Renormalize
    total = p_a + p_m + p_x
    if total > 0:
        p_a, p_m, p_x = p_a / total, p_m / total, p_x / total

    ownership = safe_float(safe_get(ownership_row, "ownership_pct", 0), 0)
    voting_power = safe_float(safe_get(ownership_row, "voting_power_pct", ownership), ownership)

    # Tilt label
    if p_a > p_m + 0.10:
        tilt_label = "Activist-leaning"
    elif p_m > p_a + 0.10:
        tilt_label = "Management-leaning"
    else:
        tilt_label = "Swing"

    return {
        "holder_id": safe_get(holder, "holder_id", ""),
        "holder_name": safe_get(holder, "name", ""),
        "holder_type": htype,
        "ownership_pct": round(ownership, 3),
        "voting_power_pct": round(voting_power, 3),
        "p_support_activist": round(probability_clamp(p_a), 3),
        "p_support_management": round(probability_clamp(p_m), 3),
        "p_abstain": round(probability_clamp(p_x), 3),
        "tilt": tilt_label,
        "governance_sensitivity_score": gov,
        "activism_support_history_score": ahs,
        "esg_sensitivity_score": esg,
        "proxy_advisor_dependence_score": safe_float(safe_get(holder, "proxy_advisor_dependence_score", 50), 50),
        "settlement_preference_score": safe_float(safe_get(holder, "settlement_preference_score", 50), 50),
        "retail_mobilization_score": safe_float(safe_get(holder, "retail_mobilization_score", 5), 5),
    }


def build_shareholder_graph(
    company,
    shareholders,
    ownership_rows,
    vulnerability,
    primary_thesis):
    """Build a networkx graph and return as a node-link dict + per-holder estimates."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    G = nx.DiGraph()
    company_node = safe_get(company, "company_id", "COMPANY")
    G.add_node(company_node, kind="company", label=safe_get(company, "name", "Company"))

    # Index shareholders by id
    sh_index = {}
    for s in shareholders or []:
        sd = s.model_dump() if hasattr(s, "model_dump") else dict(s)
        sh_index[sd.get("holder_id")] = sd

    holder_estimates: List[Dict] = []
    for o in ownership_rows or []:
        if str(safe_get(o, "company_id", "")) != str(company_node):
            continue
        hid = safe_get(o, "holder_id", "")
        h = sh_index.get(hid)
        if h is None:
            continue
        est = estimate_holder_support(h, o, company, vulnerability, primary_thesis)
        holder_estimates.append(est)

        G.add_node(hid, kind="holder", label=est["holder_name"],
                   holder_type=est["holder_type"],
                   ownership_pct=est["ownership_pct"],
                   tilt=est["tilt"])
        # Edge weighted by ownership pct
        G.add_edge(hid, company_node, weight=est["ownership_pct"], kind="owns")

    # Connect activists -> their typical archetypes (informational link)
    # Convert to node-link
    nl = json_graph.node_link_data(G, edges="links")

    return {
        "graph": nl,
        "holders": holder_estimates,
        "company_node": company_node,
        "n_holders": len(holder_estimates),
    }


def estimate_shareholder_coalition(
    holder_estimates,
    company):
    """Aggregate holder-level estimates into expected vote share."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    if not holder_estimates:
        return {
            "covered_voting_power_pct": 0.0,
            "expected_activist_vote_pct": 30.0,
            "expected_management_vote_pct": 55.0,
            "expected_abstain_pct": 15.0,
            "remaining_unattributed_pct": 100.0,
            "interpretation": "No holder data available; defaulting to neutral coalition estimates.",
            "by_holder_type": {},
        }

    total_vp = sum(h["voting_power_pct"] for h in holder_estimates)
    if total_vp <= 0:
        total_vp = 0.001

    # Weight by voting power
    w_a = sum(h["voting_power_pct"] * h["p_support_activist"] for h in holder_estimates)
    w_m = sum(h["voting_power_pct"] * h["p_support_management"] for h in holder_estimates)
    w_x = sum(h["voting_power_pct"] * h["p_abstain"] for h in holder_estimates)

    # Unattributed voting power (remaining float) split using neutral priors
    remaining = max(0.0, 100.0 - total_vp)
    # Assume retail-ish baseline for the remainder
    rp_a, rp_m, rp_x = 0.30, 0.50, 0.20
    w_a += remaining * rp_a
    w_m += remaining * rp_m
    w_x += remaining * rp_x

    total = w_a + w_m + w_x
    if total <= 0:
        total = 100.0

    pa = w_a / total * 100.0
    pm = w_m / total * 100.0
    px = w_x / total * 100.0

    # By holder type
    by_type: Dict[str, Dict] = {}
    for h in holder_estimates:
        t = h["holder_type"]
        if t not in by_type:
            by_type[t] = {"voting_power_pct": 0.0, "activist": 0.0, "management": 0.0, "abstain": 0.0}
        by_type[t]["voting_power_pct"] += h["voting_power_pct"]
        by_type[t]["activist"] += h["voting_power_pct"] * h["p_support_activist"]
        by_type[t]["management"] += h["voting_power_pct"] * h["p_support_management"]
        by_type[t]["abstain"] += h["voting_power_pct"] * h["p_abstain"]
    for t, v in by_type.items():
        vp = max(v["voting_power_pct"], 0.001)
        v["activist_share_pct"] = round(v["activist"] / vp * 100.0, 1)
        v["management_share_pct"] = round(v["management"] / vp * 100.0, 1)
        v["abstain_share_pct"] = round(v["abstain"] / vp * 100.0, 1)
        v["voting_power_pct"] = round(v["voting_power_pct"], 2)

    margin = pa - pm
    if margin > 5:
        interp = f"Activist coalition leads management by {margin:.1f}pp; meaningful pressure to settle."
    elif margin > 0:
        interp = f"Activist coalition narrowly ahead by {margin:.1f}pp; outcome could swing on PA recs and turnout."
    elif margin > -5:
        interp = f"Toss-up: management leads by {-margin:.1f}pp but vulnerable to swing-shareholder shifts."
    else:
        interp = f"Management dominates by {-margin:.1f}pp; activist would face uphill proxy fight."

    return {
        "covered_voting_power_pct": round(min(total_vp, 100.0), 2),
        "expected_activist_vote_pct": round(pa, 1),
        "expected_management_vote_pct": round(pm, 1),
        "expected_abstain_pct": round(px, 1),
        "remaining_unattributed_pct": round(remaining, 2),
        "interpretation": interp,
        "by_holder_type": by_type,
        "vote_margin_pp": round(margin, 1),
    }
