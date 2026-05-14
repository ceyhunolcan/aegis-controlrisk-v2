# Swing-shareholder scoring. Not every holder is worth a call from IR -
# index funds vote with PA, founders vote with management, activists vote
# with the activist. What matters is the *uncertain* holders weighted by
# ownership and persuasion feasibility. The Swing Value Score is a near-
# geometric mean (so a zero on any factor kills the rank), which is why
# we cap on the low end at 0.05 to avoid log-collapse.
import math

from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100, probability_clamp
)


def _uncertainty_score(holder):
    """Highest near p_activist == 0.5 (max uncertainty)."""
    p_a = safe_float(holder.get("p_support_activist", 0.4), 0.4)
    p_m = safe_float(holder.get("p_support_management", 0.5), 0.5)
    # The closer p_a and p_m are to each other, the higher the uncertainty
    diff = abs(p_a - p_m)
    return clamp((1.0 - diff) * 100.0)


def _persuasion_feasibility(holder):
    """Some holder types are easier to move; passive funds anchor on proxy advisor recs."""
    htype = str(holder.get("holder_type", "")).lower()
    base = 60.0
    if htype == "active":
        base = 80
    elif htype == "passive":
        base = 65  # via PA recommendations
    elif htype == "pension":
        base = 70
    elif htype == "retail":
        base = 30  # very hard to reach
    elif htype == "insider":
        base = 5
    elif htype == "activist":
        base = 95
    elif htype == "sovereign":
        base = 50

    # Settlement preference also increases reachability
    settle = safe_float(holder.get("settlement_preference_score", 50), 50)
    base = base + (settle - 50) * 0.3
    return clamp(base)


def _vote_importance(holder, total_voting_power):
    """Larger holders = higher importance."""
    vp = safe_float(holder.get("voting_power_pct", holder.get("ownership_pct", 0)), 0)
    if total_voting_power <= 0:
        total_voting_power = 100.0
    # 5%+ -> 100; <0.5% -> low
    pct_of_float = vp / max(total_voting_power, 1) * 100.0
    return normalize_0_100(pct_of_float, min_value=0.5, max_value=20.0)


def _settlement_influence(holder):
    """Holders with high settlement_preference and large ownership influence settlement path."""
    settle = safe_float(holder.get("settlement_preference_score", 50), 50)
    gov = safe_float(holder.get("governance_sensitivity_score", 50), 50)
    return clamp(0.6 * settle + 0.4 * gov)


def identify_swing_shareholders(
    holder_estimates,
    coalition):
    """Compute Swing Value Score for each holder and rank for outreach."""
    if not holder_estimates:
        return {
            "swing_holders": [],
            "top_5_priority_outreach": [],
            "outreach_strategy": "No holder data available.",
            "vote_threshold_analysis": {
                "votes_needed_to_majority_pp": 0.0,
                "feasibility": "unknown",
                "comment": "No coalition data.",
            },
        }

    total_vp = sum(h.get("voting_power_pct", 0) for h in holder_estimates)

    scored = []
    for h in holder_estimates:
        unc = _uncertainty_score(h)
        pers = _persuasion_feasibility(h)
        imp = _vote_importance(h, total_vp)
        infl = _settlement_influence(h)
        ownership = safe_float(h.get("voting_power_pct", h.get("ownership_pct", 0)), 0)

        # Owner-pct scaled to 100 within typical mid-cap range
        own_score = normalize_0_100(ownership, min_value=0.3, max_value=10.0)

        # Swing Value Score (per spec)
        # ownership × uncertainty × persuasion × vote_importance × settlement_influence
        svs = (own_score / 100.0) * (unc / 100.0) * (pers / 100.0) * (imp / 100.0) * (infl / 100.0)
        svs_score = clamp(svs ** 0.5 * 100.0)  # geometric mean style scaling

        # Persuasion approach
        htype = str(h.get("holder_type", "")).lower()
        if htype == "passive":
            approach = "Influence ISS/Glass Lewis recommendations; index funds follow PA on contested votes."
        elif htype == "active":
            approach = "Direct portfolio manager engagement; tailored thesis pitch with financial diligence."
        elif htype == "pension":
            approach = "Governance team engagement; emphasize fiduciary duty and long-term governance norms."
        elif htype == "retail":
            approach = "Public campaign / media + retail proxy mobilization tools."
        elif htype == "sovereign":
            approach = "Senior in-person engagement; emphasize long-term value and governance."
        elif htype == "activist":
            approach = "Coordination ('wolf pack' if appropriate); shared 13G/13D guidance."
        else:
            approach = "Direct engagement with portfolio team; tailored value/governance pitch."

        scored.append({
            "holder_id": h.get("holder_id"),
            "holder_name": h.get("holder_name"),
            "holder_type": htype,
            "voting_power_pct": round(ownership, 3),
            "uncertainty_score": round(unc, 1),
            "persuasion_feasibility_score": round(pers, 1),
            "vote_importance_score": round(imp, 1),
            "settlement_influence_score": round(infl, 1),
            "swing_value_score": round(svs_score, 1),
            "current_tilt": h.get("tilt", "Swing"),
            "recommended_persuasion_approach": approach,
        })

    scored.sort(key=lambda x: x["swing_value_score"], reverse=True)

    top5 = scored[:5]

    # Vote threshold analysis
    act_vote = safe_float(coalition.get("expected_activist_vote_pct", 0), 0)
    mgmt_vote = safe_float(coalition.get("expected_management_vote_pct", 0), 0)
    needed = max(0.0, mgmt_vote - act_vote + 1)  # need to flip a bit more than half the gap
    if act_vote > mgmt_vote:
        feasibility = "Already ahead; consolidate"
        comment = f"Activist coalition leads by {act_vote - mgmt_vote:.1f}pp; focus on holding swing holders."
    elif needed < 5:
        feasibility = "Highly feasible"
        comment = f"Only ~{needed:.1f}pp needs to flip; concentrated swing holders can deliver."
    elif needed < 12:
        feasibility = "Feasible with disciplined outreach"
        comment = f"Need to flip ~{needed:.1f}pp via top 3-5 swing holders + PA influence."
    else:
        feasibility = "Uphill"
        comment = f"Need to flip ~{needed:.1f}pp; will require either major thesis catalyst or PA endorsement."

    strategy_lines = []
    strategy_lines.append(f"Focus engagement on the top {min(5, len(scored))} swing holders by Swing Value Score.")
    strategy_lines.append(f"Combined voting power of top 5: {sum(x['voting_power_pct'] for x in top5):.1f}%.")
    strategy_lines.append("Tailor message by holder type: PA-driven for passive, financial diligence for active, governance norms for pension.")
    strategy_lines.append("Track movement quarterly via 13F changes and proxy advisor engagement signals.")

    return {
        "swing_holders": scored,
        "top_5_priority_outreach": top5,
        "outreach_strategy": " ".join(strategy_lines),
        "vote_threshold_analysis": {
            "expected_activist_vote_pct": round(act_vote, 1),
            "expected_management_vote_pct": round(mgmt_vote, 1),
            "votes_needed_to_majority_pp": round(needed, 1),
            "feasibility": feasibility,
            "comment": comment,
        },
    }
