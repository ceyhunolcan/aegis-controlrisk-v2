# Counterfactual defense optimizer. The catalogue of 12 named actions
# the board can take, plus a greedy selector that builds a defense package
# under a max-actions constraint.
#
# Greedy with diminishing returns - each subsequent action gets ~0.7x
# credit for the same headline reduction because, in practice, message
# fatigue is real and the third "we hear you and we're acting" press
# release doesn't move the needle.
from typing import Dict, List
import math

from ..utils.normalization import clamp, safe_float, safe_get


DEFENSE_ACTIONS = [
    {
        "action_id": "DA01",
        "name": "Refresh 1-2 board seats (proactive)",
        "category": "Board composition",
        "cost_score": 35,         # 0=cheap, 100=expensive
        "speed_days": 120,
        "expected_risk_reduction": 18,  # points off final risk
        "requires_consent": True,
    },
    {
        "action_id": "DA02",
        "name": "Declassify the board",
        "category": "Governance reform",
        "cost_score": 20,
        "speed_days": 270,
        "expected_risk_reduction": 12,
        "requires_consent": True,
    },
    {
        "action_id": "DA03",
        "name": "Separate CEO and Chair roles",
        "category": "Governance reform",
        "cost_score": 25,
        "speed_days": 180,
        "expected_risk_reduction": 10,
        "requires_consent": True,
    },
    {
        "action_id": "DA04",
        "name": "Adopt strong majority voting standard",
        "category": "Governance reform",
        "cost_score": 15,
        "speed_days": 90,
        "expected_risk_reduction": 7,
        "requires_consent": False,
    },
    {
        "action_id": "DA05",
        "name": "Publish capital allocation framework",
        "category": "Capital allocation",
        "cost_score": 20,
        "speed_days": 90,
        "expected_risk_reduction": 11,
        "requires_consent": False,
    },
    {
        "action_id": "DA06",
        "name": "Announce buyback / dividend boost",
        "category": "Capital allocation",
        "cost_score": 60,
        "speed_days": 60,
        "expected_risk_reduction": 9,
        "requires_consent": False,
    },
    {
        "action_id": "DA07",
        "name": "Initiate strategic review of underperforming segment",
        "category": "Strategic",
        "cost_score": 50,
        "speed_days": 120,
        "expected_risk_reduction": 14,
        "requires_consent": False,
    },
    {
        "action_id": "DA08",
        "name": "Pre-emptive engagement: top 25 holders",
        "category": "Shareholder engagement",
        "cost_score": 25,
        "speed_days": 60,
        "expected_risk_reduction": 13,
        "requires_consent": False,
    },
    {
        "action_id": "DA09",
        "name": "Compensation framework reset (long-term TSR-linked)",
        "category": "Compensation",
        "cost_score": 35,
        "speed_days": 120,
        "expected_risk_reduction": 11,
        "requires_consent": True,
    },
    {
        "action_id": "DA10",
        "name": "ESG / climate transition plan publication",
        "category": "ESG",
        "cost_score": 30,
        "speed_days": 90,
        "expected_risk_reduction": 8,
        "requires_consent": False,
    },
    {
        "action_id": "DA11",
        "name": "Adopt narrow / low-threshold poison pill",
        "category": "Defensive structural",
        "cost_score": 30,
        "speed_days": 30,
        "expected_risk_reduction": 6,  # Mostly buys time, doesn't reduce true risk much
        "requires_consent": False,
    },
    {
        "action_id": "DA12",
        "name": "Proxy advisor pre-engagement (ISS / Glass Lewis)",
        "category": "Proxy advisor",
        "cost_score": 15,
        "speed_days": 45,
        "expected_risk_reduction": 9,
        "requires_consent": False,
    },
]


def generate_defense_actions():
    """Return the canonical action list."""
    return [dict(a) for a in DEFENSE_ACTIONS]


def _diminishing_returns(total_actions):
    """Each additional action contributes less; cap aggregated reduction."""
    # 5 actions ≈ 90% of theoretical max; sqrt scaling
    return 1.0 - math.exp(-total_actions / 3.5)


def _contextual_adjustment(action, context):
    """Tweak an action's expected risk reduction based on context."""
    base = float(action["expected_risk_reduction"])
    company = context.get("company", {})
    vulnerability = context.get("vulnerability", {})
    pa_view = context.get("pa_view", {})

    v = safe_float(vulnerability.get("score", 50), 50)
    pa_gov = safe_float(pa_view.get("pa_governance_concern_score", 50), 50) if pa_view else 50

    aid = action["action_id"]
    if aid == "DA02" and bool(safe_get(company, "classified_board", False)):
        base += 5  # Declassification matters a lot if currently classified
    if aid == "DA03" and bool(safe_get(company, "ceo_chair_combined", False)):
        base += 4
    if aid == "DA12" and pa_gov > 60:
        base += 4
    if aid == "DA11" and bool(safe_get(company, "has_poison_pill", False)):
        base = 2  # already have one
    if aid == "DA10" and "energy" in str(safe_get(company, "sector", "")).lower():
        base += 5
    if aid == "DA01" and v > 65:
        base += 3
    return clamp(base, 0, 30)


def optimize_defense_package(
    actions = None,
    company = None,
    vulnerability = None,
    pa_view = None,
    initial_risk_score = 60.0,
    max_actions = 5):
    """Choose an optimal package of up to `max_actions` defense actions."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    context = {"company": company, "vulnerability": vulnerability or {}, "pa_view": pa_view or {}}
    pool = actions if actions else generate_defense_actions()

    # Score each action by adjusted reduction / cost
    scored = []
    for a in pool:
        adj = _contextual_adjustment(a, context)
        # Efficiency: reduction per cost unit (+ speed bonus)
        cost = max(a["cost_score"], 1)
        speed_bonus = max(0, (180 - a["speed_days"]) / 180.0) * 5  # quicker = higher
        efficiency = adj / cost * 100 + speed_bonus
        scored.append({**a, "adjusted_reduction": round(adj, 2), "efficiency": round(efficiency, 2)})

    # Greedy: pick top by efficiency, ensure diversity (at most 1 from "Defensive structural")
    scored.sort(key=lambda x: x["efficiency"], reverse=True)
    chosen: List[Dict] = []
    cats = set()
    for s in scored:
        if len(chosen) >= max_actions:
            break
        # Cap "Defensive structural" to 1
        if s["category"] == "Defensive structural" and "Defensive structural" in cats:
            continue
        chosen.append(s)
        cats.add(s["category"])

    # Compute aggregated reduction
    raw_sum = sum(c["adjusted_reduction"] for c in chosen)
    dr_factor = _diminishing_returns(len(chosen))
    expected_reduction = clamp(raw_sum * dr_factor, 0, initial_risk_score)

    risk_before = clamp(initial_risk_score)
    risk_after = clamp(risk_before - expected_reduction)

    # 90-day plan
    plan: List[Dict] = []
    short_term = [c for c in chosen if c["speed_days"] <= 60]
    mid_term = [c for c in chosen if 60 < c["speed_days"] <= 120]
    long_term = [c for c in chosen if c["speed_days"] > 120]

    for c in short_term:
        plan.append({"timing": "Days 0-30", "action": c["name"], "category": c["category"],
                     "expected_reduction": c["adjusted_reduction"]})
    for c in mid_term:
        plan.append({"timing": "Days 30-90", "action": c["name"], "category": c["category"],
                     "expected_reduction": c["adjusted_reduction"]})
    for c in long_term:
        plan.append({"timing": "Beyond Day 90", "action": c["name"], "category": c["category"],
                     "expected_reduction": c["adjusted_reduction"]})

    summary = (
        f"Recommended package of {len(chosen)} actions reduces modeled activism risk score "
        f"from {risk_before:.1f} to {risk_after:.1f} (reduction {expected_reduction:.1f} points)."
    )

    return {
        "recommended_actions": chosen,
        "max_actions": max_actions,
        "estimated_risk_before": round(risk_before, 1),
        "estimated_risk_after": round(risk_after, 1),
        "estimated_risk_reduction": round(expected_reduction, 1),
        "ninety_day_plan": plan,
        "all_actions_scored": scored,
        "summary": summary,
    }
