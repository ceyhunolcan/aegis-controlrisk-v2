# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Bank-mandate opportunity scorer. The same picture as the activism risk
# score, but read from the sell-side coverage banker's perspective: which
# at-risk clients are most likely to *need* an advisor in the next 12m,
# and what products would we pitch? Risk level + control-loss potential
# drive most of the score because banks get hired when boards are scared,
# not when they're complacent.
from typing import List

from ..utils.normalization import clamp, safe_float, safe_get, normalize_0_100


WEIGHTS = {
    "risk_level": 0.25,
    "control_loss_potential": 0.20,
    "urgency": 0.15,
    "complexity": 0.15,
    "size": 0.10,
    "board_sensitivity": 0.10,
    "visibility": 0.05,
}


def _opportunity_level(score):
    if score >= 75:
        return "Top-priority mandate"
    if score >= 60:
        return "Priority mandate"
    if score >= 45:
        return "Watchlist mandate"
    return "Low-priority"


def _likely_products(
    company, final_score, settlement, defense):
    products: List[str] = []
    products.append("Defense advisory (proxy/M&A defense)")
    products.append("Shareholder engagement & investor relations support")
    products.append("Proxy solicitation & vote management")
    products.append("Strategic alternatives review")
    if safe_float(final_score.get("control_loss_probability_if_attacked", 0.3), 0.3) > 0.4:
        products.append("Board composition & nominee identification")
    if bool(safe_get(company, "controlled_company_flag", False)) or bool(safe_get(company, "dual_class_flag", False)):
        products.append("Governance restructuring counsel")
    if "strategic" in str(safe_get(settlement, "best_option", {}).get("option_name", "")).lower():
        products.append("Sell-side M&A advisory")
    products.append("Bondholder/credit-side defense (where relevant)")
    return products[:8]


def _pitch_angle(company, final_score, vulnerability):
    v = safe_float(vulnerability.get("score", 50), 50)
    fr = final_score.get("final_risk_level", "Moderate")
    cname = safe_get(company, "name", "the target")
    return (
        f"{cname} screens {fr.lower()} for activism risk (vulnerability {v:.0f}/100). "
        f"Pitch a coordinated defense engagement now to lock in the mandate before the campaign window opens. "
        f"Lead with proxy/M&A defense and shareholder engagement; pull in M&A advisory if a strategic review surfaces."
    )


def _client_email(company, pitch, banker_name = "[Banker]"):
    cname = safe_get(company, "name", "[Company]")
    lines = [
        f"Subject: {cname} — board-level preparedness for activism risk",
        "",
        "Dear [CEO/Chair],",
        "",
        f"Our team has refreshed our analysis of {cname}'s shareholder and governance posture.",
        "We see a meaningful uptick in activism-related signal across vulnerability, board composition,",
        "and shareholder coalition exposure relative to peers.",
        "",
        "Over the next ten days we would value the opportunity to walk the board through:",
        "  • The most likely activist archetypes and theses we would expect to see deployed",
        "  • A board-level vulnerability map and proactive defense roadmap",
        "  • A targeted shareholder engagement plan for the top decile of holders",
        "",
        "We can be available at your convenience and would propose a 60-minute session with the lead",
        "independent director and chair of governance.",
        "",
        "Best regards,",
        f"{banker_name}",
    ]
    return "\n".join(lines)


def _board_pitch(company, final_score, settlement):
    cname = safe_get(company, "name", "the Company")
    fr = final_score.get("final_risk_level", "Moderate")
    best = settlement.get("best_option", {}) if settlement else {}
    return (
        f"Board briefing: {cname} sits in the '{fr}' band of activism risk based on integrated CASCADE-2 signals. "
        f"Recommended posture is '{best.get('option_name', 'Engage and explore')}'. "
        f"Engagement scope: proactive defense, shareholder mapping, claim-by-claim response framework, "
        f"and PA pre-engagement. We are well-positioned to lead this on a sole or co-advisor basis."
    )


def score_bank_mandate_opportunity(
    company,
    final_score,
    vulnerability,
    fixability,
    legal_calendar,
    triggers,
    settlement,
    defense):
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    # Component scores
    final_risk = safe_float(final_score.get("activism_risk_score_0_100", 50), 50) if final_score else 50
    risk_level_score = clamp(final_risk)

    control_loss_p = safe_float(final_score.get("control_loss_probability_if_attacked", 0.3), 0.3) if final_score else 0.3
    control_loss_score = clamp(control_loss_p * 100)

    urgency_score = safe_float(triggers.get("trigger_score", 30), 30) if triggers else 30
    # Combine with legal calendar urgency
    leg_urg = safe_float(legal_calendar.get("urgency_score", 30), 30) if legal_calendar else 30
    urgency_score = clamp(0.6 * urgency_score + 0.4 * leg_urg)

    # Complexity: dual class / controlled / classified / strategic = more complex = more fees
    complexity = 40
    if bool(safe_get(company, "controlled_company_flag", False)):
        complexity += 25
    if bool(safe_get(company, "dual_class_flag", False)):
        complexity += 18
    if bool(safe_get(company, "classified_board", False)):
        complexity += 10
    if "review" in str(settlement.get("best_option", {}).get("option_name", "")).lower():
        complexity += 12
    complexity = clamp(complexity)

    # Size: market cap
    mc = safe_float(safe_get(company, "market_cap", 0), 0) / 1e9  # in $B
    size_score = normalize_0_100(mc, min_value=1.0, max_value=200.0)

    # Board sensitivity: weak defense + high vulnerability = sensitive board
    v = safe_float(vulnerability.get("score", 50), 50)
    d = safe_float(defense.get("defense_strength_score", 50), 50)
    board_sensitivity = clamp((v - d + 50))

    # Visibility: media / market cap / well-known industries
    visibility = clamp(40 + size_score * 0.3 + (final_risk - 50) * 0.5)

    components = {
        "risk_level": risk_level_score,
        "control_loss_potential": control_loss_score,
        "urgency": urgency_score,
        "complexity": complexity,
        "size": size_score,
        "board_sensitivity": board_sensitivity,
        "visibility": visibility,
    }
    score = sum(components[k] * w for k, w in WEIGHTS.items())
    score = clamp(score)
    level = _opportunity_level(score)

    products = _likely_products(company, final_score or {}, settlement or {}, defense or {})
    pitch = _pitch_angle(company, final_score or {}, vulnerability or {})
    email = _client_email(company, pitch)
    board_summary = _board_pitch(company, final_score or {}, settlement or {})

    return {
        "mandate_opportunity_score": round(score, 1),
        "opportunity_level": level,
        "components": components,
        "likely_advisory_products": products,
        "banker_pitch_angle": pitch,
        "suggested_client_email": email,
        "board_meeting_pitch_summary": board_summary,
    }
