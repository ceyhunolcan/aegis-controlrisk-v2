# Probability-weighted stock reaction. Six discrete scenarios (announcement,
# preemptive defense, settle 1 seat, settle 2 seats, full defense, strategic
# review), each with a baseline 1-day reaction and a volatility band. Output
# is a single expected reaction in percentage points, weighted by the
# scenario probabilities from the MC.
#
# Calibration: these are sample-mean reactions from public campaigns,
# 2018-2024. Settle-and-review reactions are larger than people expect
# because the market reads strategic-review settlements as "company is
# selling at a premium soon" more often than not.
from typing import Dict, List

from ..utils.normalization import clamp, safe_float, safe_get, probability_clamp


SCENARIOS = [
    {
        "scenario_id": "activist_announced",
        "name": "Activist publicly announced (13D)",
        "baseline_reaction_pp": +3.5,
        "volatility_pp": 4.0,
    },
    {
        "scenario_id": "preemptive_defense",
        "name": "Pre-emptive defense package announced",
        "baseline_reaction_pp": +1.0,
        "volatility_pp": 2.5,
    },
    {
        "scenario_id": "settle_1_seat",
        "name": "Settlement: 1 activist seat",
        "baseline_reaction_pp": +2.5,
        "volatility_pp": 2.5,
    },
    {
        "scenario_id": "settle_2_seats",
        "name": "Settlement: 2 activist seats",
        "baseline_reaction_pp": +3.5,
        "volatility_pp": 3.0,
    },
    {
        "scenario_id": "full_defense",
        "name": "Management full defense / company wins",
        "baseline_reaction_pp": -1.5,
        "volatility_pp": 3.5,
    },
    {
        "scenario_id": "strategic_review",
        "name": "Strategic review announced",
        "baseline_reaction_pp": +6.0,
        "volatility_pp": 4.0,
    },
]


def _adjust_for_company(scenario, company, vulnerability, fixability, thesis):
    """Adjust scenario's baseline reaction by company specifics."""
    base = scenario["baseline_reaction_pp"]
    v = safe_float(vulnerability.get("score", 50), 50)
    f = safe_float(fixability.get("score", 50), 50)
    upside = str(thesis.get("estimated_upside_range", "")) if thesis else ""

    # High vulnerability + high fixability => market sees more upside in activist scenarios
    upside_lift = ((v - 50) / 100.0) * 2 + ((f - 50) / 100.0) * 2

    if scenario["scenario_id"] in ("activist_announced", "settle_1_seat", "settle_2_seats", "strategic_review"):
        base += upside_lift
    elif scenario["scenario_id"] == "full_defense":
        base -= max(0, upside_lift)  # if upside was there, full defense forgoes it
    elif scenario["scenario_id"] == "preemptive_defense":
        base += upside_lift * 0.5

    # Controlled company dampens reaction
    if bool(safe_get(company, "controlled_company_flag", False)):
        base *= 0.6

    return base


def simulate_market_reaction(
    company,
    vulnerability,
    fixability,
    primary_thesis,
    simulation_result):
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    reactions: List[Dict] = []
    for scen in SCENARIOS:
        adj = _adjust_for_company(scen, company, vulnerability or {}, fixability or {}, primary_thesis or {})
        low = adj - scen["volatility_pp"]
        high = adj + scen["volatility_pp"]
        reactions.append({
            "scenario_id": scen["scenario_id"],
            "scenario_name": scen["name"],
            "expected_reaction_pp": round(adj, 2),
            "p10_reaction_pp": round(low, 2),
            "p90_reaction_pp": round(high, 2),
            "volatility_pp": scen["volatility_pp"],
            "narrative": _scenario_narrative(scen["scenario_id"], adj, company, primary_thesis),
        })

    # Weight scenarios by simulation probabilities
    p_priv = safe_float(simulation_result.get("p_private_settlement", 0.3), 0.3) if simulation_result else 0.3
    p_strat = safe_float(simulation_result.get("p_strategic_review", 0.05), 0.05) if simulation_result else 0.05
    p_full_def = safe_float(simulation_result.get("p_company_full_defense", 0.4), 0.4) if simulation_result else 0.4
    p_proxy = safe_float(simulation_result.get("p_proxy_vote", 0.4), 0.4) if simulation_result else 0.4

    # Map to scenarios (rough)
    weights = {
        "activist_announced": 0.15,
        "preemptive_defense": 0.10,
        "settle_1_seat": p_priv * 0.5,
        "settle_2_seats": p_priv * 0.4,
        "full_defense": p_full_def * 0.6,
        "strategic_review": p_strat,
    }
    # Normalize
    total = sum(weights.values())
    if total <= 0:
        total = 1.0
    weights = {k: v / total for k, v in weights.items()}

    weighted = 0.0
    for r in reactions:
        weighted += r["expected_reaction_pp"] * weights.get(r["scenario_id"], 0)

    # Risk to stock story
    if weighted < 0:
        risk = (
            "Market-weighted expected reaction is modestly negative; defending without delivering "
            "operational momentum risks underperformance vs peers."
        )
    elif weighted > 3:
        risk = (
            "Market-weighted reaction is strongly positive across settlement and review scenarios — "
            "an indication the market expects change to unlock value."
        )
    else:
        risk = (
            "Market-weighted reaction is mildly positive; mix of outcomes priced in but no strong bias."
        )

    return {
        "scenario_reactions": reactions,
        "scenario_weights": {k: round(v, 3) for k, v in weights.items()},
        "expected_reaction_weighted_pp": round(weighted, 2),
        "risk_to_stock_story": risk,
    }


def _scenario_narrative(sid, reaction, company, thesis):
    cname = safe_get(company, "name", "the Company")
    sign = "positive" if reaction >= 0 else "negative"
    if sid == "activist_announced":
        return f"13D filing typically prompts a {sign} {abs(reaction):.1f}pp move at {cname} as the market prices in change optionality."
    if sid == "preemptive_defense":
        return f"Pre-emptive defense signals confidence; modest {sign} reaction of {abs(reaction):.1f}pp."
    if sid == "settle_1_seat":
        return f"One-seat settlement is read as a measured concession; ~{abs(reaction):.1f}pp {sign} move."
    if sid == "settle_2_seats":
        return f"Two-seat settlement implies real influence; ~{abs(reaction):.1f}pp {sign} move."
    if sid == "full_defense":
        return f"Full defense preserves status quo; ~{abs(reaction):.1f}pp {sign} reaction unless paired with credible plan."
    if sid == "strategic_review":
        return f"Strategic review headline tends to drive the largest single reaction (~{abs(reaction):.1f}pp {sign})."
    return ""
