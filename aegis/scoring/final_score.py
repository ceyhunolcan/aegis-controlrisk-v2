# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# The headline number. Combines vulnerability + control-loss probability
# + settlement pressure into a single 0-100 figure, then maps to a level.
# Two ways to escalate: composite >= threshold, OR both event-prob and
# control-loss-prob simultaneously high (escalates one notch). The latter
# rule catches "controlled but vulnerable" cases where the composite
# score is moderate but the situation is genuinely dangerous.
from ..utils.normalization import clamp, safe_float, safe_get, probability_clamp
from config import RISK_LEVELS


def _final_risk_level(activism_risk_score, activism_p = None,
                      control_loss_p = None):
    """Map the composite 0-100 activism risk score to a level using the
    thresholds defined in config.RISK_LEVELS. Probability-based escalation:
    if both activism_p and control_loss_p are high, escalate one level up.
    """
    s = float(activism_risk_score)
    # Base level from composite score
    if s >= RISK_LEVELS["Critical"]:
        level = "Critical"
    elif s >= RISK_LEVELS["High"]:
        level = "High"
    elif s >= RISK_LEVELS["Moderate"]:
        level = "Moderate"
    else:
        level = "Low"

    # Probability-based escalation: a near-certain campaign with high control-loss
    # bumps "High" -> "Critical" even if composite < 80
    if (activism_p is not None and control_loss_p is not None
            and activism_p >= 0.70 and control_loss_p >= 0.50):
        if level == "High":
            level = "Critical"
        elif level == "Moderate":
            level = "High"
    return level


def calculate_final_controlrisk_score(
    company,
    vulnerability,
    fixability,
    legal_calendar,
    triggers,
    coalition,
    pa_view,
    simulation_result,
    defense_result,
    settlement_result,
    primary_thesis,
    activist_dna_top):
    """Compute the final ControlRisk composite score and exec summary."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    v = safe_float(vulnerability.get("score", 50), 50)
    f = safe_float(fixability.get("score", 50), 50)
    leg = safe_float(legal_calendar.get("legal_feasibility_score", 50), 50)
    trig = safe_float(triggers.get("trigger_score", 30), 30)
    act_coal = safe_float(coalition.get("expected_activist_vote_pct", 35), 35)
    p_pa_one = safe_float(pa_view.get("p_support_one_activist_nominee", 0.3), 0.3)

    # Activism event probability (12m) — likelihood of P(starts × traction)
    # Higher when vulnerability + fixability + triggers + legal feasibility align
    p_start = (0.30 * v + 0.20 * f + 0.20 * trig + 0.15 * leg) / 100.0  # 0..0.85 baseline
    p_start = clamp(p_start + 0.10, 0, 1)
    # Activist DNA strong fit raises this
    if activist_dna_top:
        fit = safe_float(activist_dna_top.get("fit_score", 50), 50)
        p_start = clamp(p_start + (fit - 50) / 100.0 * 0.30, 0, 1)
    # Controlled co reduces real probability
    if bool(safe_get(company, "controlled_company_flag", False)):
        p_start *= 0.55

    p_traction = clamp(0.5 + (act_coal - 35) / 100.0 * 0.6 + (p_pa_one - 0.3) * 0.3, 0, 1)

    activism_event_p_12m = probability_clamp(p_start * 0.85 + p_traction * 0.15)
    # Simpler form: take the start probability since traction is conditional
    activism_event_p_12m = probability_clamp(p_start * 0.7 + p_traction * 0.3 * p_start)
    activism_event_p_12m = clamp(activism_event_p_12m, 0, 1)

    # Control-loss probability if attacked
    p_act_wins_2_plus = safe_float(simulation_result.get("p_activist_wins_2_plus", 0.2), 0.2)
    p_act_wins_1_plus = safe_float(simulation_result.get("p_activist_wins_1_plus", 0.4), 0.4)
    p_full_def = safe_float(simulation_result.get("p_company_full_defense", 0.4), 0.4)
    defense_strength = safe_float(defense_result.get("defense_strength_score", 50), 50)

    # control-loss = activist wins enough seats to materially shape board
    control_loss_p = probability_clamp(0.5 * p_act_wins_2_plus + 0.3 * p_act_wins_1_plus + 0.2 * (1 - p_full_def))
    # Adjust for legal protections
    if bool(safe_get(company, "controlled_company_flag", False)):
        control_loss_p *= 0.4
    if bool(safe_get(company, "classified_board", False)):
        control_loss_p *= 0.7

    # Board seat loss probability is essentially p_act_wins_1_plus tempered by defense
    board_seat_loss_p = probability_clamp(p_act_wins_1_plus * (1 - 0.2 * (defense_strength - 50) / 100.0))

    # Settlement pressure index 0-100: how badly mgmt wants to settle
    # = function of (activism_p_12m, control_loss, weak defense, high coalition)
    sp = (
        40 * activism_event_p_12m +
        30 * control_loss_p +
        20 * (1 - defense_strength / 100.0) +
        10 * (act_coal / 100.0)
    )
    settlement_pressure_index = clamp(sp)

    # Activism risk 0-100 score (composite — single headline figure)
    activism_risk_score = clamp(
        0.40 * (activism_event_p_12m * 100) +
        0.30 * (control_loss_p * 100) +
        0.15 * settlement_pressure_index +
        0.15 * v
    )

    final_level = _final_risk_level(activism_risk_score, activism_event_p_12m, control_loss_p)

    # Executive summary
    cname = safe_get(company, "name", "the Company")
    thesis_name = safe_get(primary_thesis, "name", "Board Refresh + Capital Discipline")
    archetype = safe_get(activist_dna_top, "name", "Constructive activist") if activist_dna_top else "Constructive activist"

    summary = (
        f"{cname} is rated {final_level} on the CASCADE-2 ControlRisk scale "
        f"(score {activism_risk_score:.0f}/100). "
        f"Modeled 12-month activism event probability is {activism_event_p_12m*100:.0f}%. "
        f"Conditional on an attack, control-loss probability is {control_loss_p*100:.0f}%. "
        f"Primary thesis likely to be deployed: '{thesis_name}'. "
        f"Likely activist archetype: {archetype}. "
        f"Settlement pressure index: {settlement_pressure_index:.0f}/100. "
        f"This is not legal or investment advice."
    )

    return {
        "activism_event_probability_12m": round(activism_event_p_12m, 3),
        "control_loss_probability_if_attacked": round(control_loss_p, 3),
        "board_seat_loss_probability": round(board_seat_loss_p, 3),
        "settlement_pressure_index": round(settlement_pressure_index, 1),
        "activism_risk_score_0_100": round(activism_risk_score, 1),
        "final_risk_level": final_level,
        "executive_summary": summary,
    }
