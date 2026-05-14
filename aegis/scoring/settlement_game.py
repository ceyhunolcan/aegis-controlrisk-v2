# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Settle-vs-fight game. Eight discrete options on the continuum from "fight
# all the way to a vote" to "hand over the board". Each gets scored on a
# utility function blending risk reduction, shareholder acceptance, board
# control retained, activist satisfaction (yes, that matters - settled
# activists don't come back next year), governance cost, and disruption.
# The recommendation surfaces the best + runner-up so the board sees both.
from ..utils.normalization import clamp, safe_float, safe_get, probability_clamp


OPTIONS = [
    {"id": "fight_full", "name": "Fight publicly through proxy contest", "settlement_pct": 0.0},
    {"id": "preemptive_defense", "name": "Pre-emptive defense (no negotiation yet)", "settlement_pct": 0.05},
    {"id": "engage_explore", "name": "Engage to explore (no concessions yet)", "settlement_pct": 0.15},
    {"id": "concede_governance", "name": "Concede governance reforms only", "settlement_pct": 0.25},
    {"id": "settle_1_seat", "name": "Settle: 1 activist board seat", "settlement_pct": 0.45},
    {"id": "settle_2_seats", "name": "Settle: 2 activist board seats", "settlement_pct": 0.65},
    {"id": "settle_3_seats_strategic_review", "name": "Settle: 2-3 seats + strategic review", "settlement_pct": 0.80},
    {"id": "full_settlement", "name": "Full settlement / activist takes board control", "settlement_pct": 1.00},
]


# Utility component weights (per spec)
UTIL_WEIGHTS = {
    "risk_reduction": 0.30,
    "shareholder_acceptance": 0.20,
    "board_control_retained": 0.20,
    "activist_satisfaction": 0.15,
    "governance_cost": -0.10,  # Higher cost reduces utility
    "operating_disruption": -0.05,
}


def _utility_for_option(option, sim, defense, coalition):
    """Score an option on each utility dimension."""
    s = option["settlement_pct"]

    p_act_wins = safe_float(safe_get(sim, "p_activist_wins_1_plus", 0.4), 0.4)
    defense_score = safe_float(safe_get(defense, "defense_strength_score", 50), 50)
    activist_coal = safe_float(safe_get(coalition, "expected_activist_vote_pct", 40), 40)

    # Risk reduction: settling reduces residual proxy risk; depends on how strong defense is too
    # Fighting full is high-risk if defense is weak.
    if s == 0.0:
        risk_reduction = clamp(defense_score - 50 + 50)  # If defense strong, fighting reduces risk
    else:
        risk_reduction = clamp(40 + s * 50)

    # Shareholder acceptance: settling tends to be well-received if activist coalition is strong
    if activist_coal > 50:
        sh_accept = clamp(30 + s * 60)
    else:
        sh_accept = clamp(75 - s * 30)

    # Board control retained: linear with (1 - s)
    board_control = clamp((1 - s) * 100)

    # Activist satisfaction: linear with s
    activist_sat = clamp(s * 100)

    # Governance cost: rises with seats granted + strategic review concessions
    governance_cost = clamp(s * 80)

    # Operating disruption: fighting publicly is disruptive; full settlement also disruptive
    if s == 0.0:
        disruption = 75
    elif s >= 0.80:
        disruption = 65
    elif s == 0.05:
        disruption = 45
    else:
        disruption = clamp(20 + abs(s - 0.45) * 40)

    return {
        "risk_reduction": risk_reduction,
        "shareholder_acceptance": sh_accept,
        "board_control_retained": board_control,
        "activist_satisfaction": activist_sat,
        "governance_cost": governance_cost,
        "operating_disruption": disruption,
    }


def _utility_score(components):
    score = 50.0
    for k, w in UTIL_WEIGHTS.items():
        score += (components[k] - 50) * w
    return clamp(score)


def evaluate_settlement_options(
    company,
    primary_thesis,
    director_scores,
    coalition,
    pa_view,
    simulation_result,
    defense_result):
    """Evaluate each option, recommend a path, and produce a negotiation script."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    sim = simulation_result or {}
    defense = defense_result or {}
    coalition = coalition or {}

    options = []
    for opt in OPTIONS:
        comps = _utility_for_option(opt, sim, defense, coalition)
        u = _utility_score(comps)
        # Apply context overrides
        if bool(safe_get(company, "controlled_company_flag", False)) and opt["id"] in ("fight_full", "preemptive_defense"):
            u += 8  # controlled companies can fight more easily
        if safe_float(safe_get(defense, "defense_strength_score", 50), 50) > 70 and opt["id"] in ("fight_full",):
            u += 5
        elif safe_float(safe_get(defense, "defense_strength_score", 50), 50) < 40 and opt["id"] in ("fight_full",):
            u -= 10

        options.append({
            "option_id": opt["id"],
            "option_name": opt["name"],
            "settlement_pct": opt["settlement_pct"],
            "components": {k: round(v, 1) for k, v in comps.items()},
            "utility_score": round(clamp(u), 1),
        })

    options.sort(key=lambda x: x["utility_score"], reverse=True)
    best = options[0]
    runner_up = options[1] if len(options) > 1 else options[0]

    # Recommended path
    if best["option_id"] in ("fight_full", "preemptive_defense"):
        path = "Defend"
    elif best["option_id"] in ("engage_explore", "concede_governance"):
        path = "Engage and explore"
    else:
        path = "Settle"

    # Negotiation script
    script_lines = []
    script_lines.append("NEGOTIATION SCRIPT (boardroom-ready, paraphraseable)")
    script_lines.append("")
    script_lines.append(f"Recommended posture: {best['option_name']}")
    script_lines.append("")
    script_lines.append("Opening line (to activist):")
    if best["option_id"] in ("settle_1_seat", "settle_2_seats", "settle_3_seats_strategic_review"):
        seats = "one seat" if "1_seat" in best["option_id"] else "up to two seats" if "2_seats" in best["option_id"] else "two to three seats and a strategic review"
        script_lines.append(
            f"  'We have reviewed the issues you have raised and are prepared to discuss a constructive arrangement that "
            f"includes {seats}, alongside a defined work plan and standstill, in a way that preserves shareholder optionality.'"
        )
    elif best["option_id"] in ("fight_full", "preemptive_defense"):
        script_lines.append(
            "  'We have considered your views and respectfully disagree on the prescription. The board's plan is on track, "
            "and we will recommend our full slate to shareholders. We remain open to engagement on substantive issues, "
            "without conceding the strategic direction.'"
        )
    else:
        script_lines.append(
            "  'We appreciate your engagement and are prepared to expand our dialogue. Before any structural commitments, "
            "we propose a working session to align on diagnosis and to test whether our and your perspectives converge.'"
        )
    script_lines.append("")
    script_lines.append("Walk-away conditions:")
    script_lines.append("  - Demands that exceed proportional representation given activist economics")
    script_lines.append("  - Demands that lock the board into a specific transaction or timeline beyond fiduciary discretion")
    script_lines.append("  - Loss of CEO succession authority or compensation independence")
    script_lines.append("")
    script_lines.append("Internal review checkpoints:")
    script_lines.append("  - Pre-meeting: align with lead independent director + chair of governance committee")
    script_lines.append("  - Mid-negotiation: refresh proxy advisor read on settlement vs. contest")
    script_lines.append("  - Closing: confirm shareholder-base communication plan and 90-day post-settlement plan")
    script_lines.append("")
    script_lines.append("This is not legal advice. Final settlement terms should be drafted with proxy/legal counsel.")
    script = "\n".join(script_lines)

    summary = (
        f"Recommended path: '{best['option_name']}' (utility {best['utility_score']:.1f}). "
        f"Runner-up: '{runner_up['option_name']}' (utility {runner_up['utility_score']:.1f})."
    )

    return {
        "recommended_path": path,
        "best_option": best,
        "runner_up_option": runner_up,
        "options": options,
        "negotiation_script": script,
        "summary": summary,
    }
