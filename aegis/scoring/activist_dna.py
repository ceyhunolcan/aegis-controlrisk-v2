# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Activist DNA matching. Given a target, rank the eight archetypes by how
# well they fit. The fit blend was tuned empirically against historical
# campaigns - market cap fit matters more than you'd think (most activists
# size their funds for a specific cap band) and thesis alignment matters
# more than aggressiveness preferences.
from typing import List

from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100
)


def _market_cap_fit(company, archetype):
    mc = safe_float(safe_get(company, "market_cap", 0.0), 0.0)
    lo = safe_float(safe_get(archetype, "preferred_market_cap_min", 0.0), 0.0)
    hi = safe_float(safe_get(archetype, "preferred_market_cap_max", 1e15), 1e15)
    if mc <= 0:
        return 50.0
    if lo <= mc <= hi:
        # Fit best in the middle of the range
        if hi > lo:
            mid = (lo + hi) / 2
            spread = (hi - lo) / 2
            dist = abs(mc - mid) / max(spread, 1)
            return clamp(100.0 - dist * 30.0)
        return 80.0
    if mc < lo:
        gap = (lo - mc) / max(lo, 1)
        return clamp(50.0 - gap * 50.0)
    gap = (mc - hi) / max(hi, 1)
    return clamp(50.0 - gap * 50.0)


def _thesis_alignment(archetype, vulnerability, company):
    """How well archetype weights match the company's vulnerability profile."""
    comps = vulnerability.get("components", {}) if isinstance(vulnerability, dict) else {}
    value = clamp(0.55 * comps.get("valuation_discount", 50) +
                  0.45 * comps.get("roic_margin_gap", 50))
    operational = clamp(0.50 * comps.get("roic_margin_gap", 50) +
                        0.30 * comps.get("strategic_confusion", 50) +
                        0.20 * comps.get("capital_allocation_weakness", 50))
    governance = comps.get("governance_weakness", 50)
    esg = 60.0 if str(safe_get(company, "sector", "")) in {"Energy", "Materials", "Utilities"} else 35.0

    # Weight by archetype preference (out of typical 0-100)
    w_val = safe_float(safe_get(archetype, "value_weight", 0), 0) / 100.0
    w_op = safe_float(safe_get(archetype, "operational_weight", 0), 0) / 100.0
    w_gov = safe_float(safe_get(archetype, "governance_weight", 0), 0) / 100.0
    w_esg = safe_float(safe_get(archetype, "esg_weight", 0), 0) / 100.0
    total = w_val + w_op + w_gov + w_esg
    if total <= 0:
        return 50.0
    return clamp((w_val * value + w_op * operational + w_gov * governance +
                  w_esg * esg) / total)


def _settlement_alignment(archetype, fixability, company):
    """Settlement-prefering activists pair with more controllable, midrange situations."""
    fix_score = safe_float(safe_get(fixability, "score", 50), 50) if isinstance(fixability, dict) else 50.0
    sp = safe_float(safe_get(archetype, "settlement_preference", 50), 50)
    # If controlled, only settlement-leaning archetypes have any traction
    if safe_get(company, "controlled_company_flag", False) or safe_get(company, "dual_class_flag", False):
        return clamp(sp * 0.7 + 20)
    # When fixability is high, both styles work but settlement-prone archetypes get a small bump
    return clamp(0.65 * fix_score + 0.35 * sp)


def _likely_campaign_style(archetype, vulnerability, company):
    style = str(safe_get(archetype, "style", "public letter"))
    # If governance feasibility low and aggression high, downgrade style
    if safe_get(company, "controlled_company_flag", False) and style not in {"quiet engagement", "ESG/transition campaign"}:
        return "public letter (high difficulty due to control structure)"
    return style


def score_activist_archetype_fit(
    company,
    financials,
    vulnerability,
    fixability,
    archetype):
    """Score one archetype's fit against the target company."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if hasattr(financials, "model_dump"):
        financials = financials.model_dump()
    if hasattr(archetype, "model_dump"):
        archetype = archetype.model_dump()

    mc_fit = _market_cap_fit(company, archetype)
    thesis_fit = _thesis_alignment(archetype, vulnerability, company)
    settle_fit = _settlement_alignment(archetype, fixability, company)
    vuln_score = safe_float(safe_get(vulnerability, "score", 50), 50) if isinstance(vulnerability, dict) else 50.0

    fit_score = clamp(0.30 * mc_fit + 0.40 * thesis_fit +
                      0.15 * settle_fit + 0.15 * vuln_score)

    likely_stake = safe_float(safe_get(archetype, "typical_stake_pct", 3.0), 3.0)
    likely_seats = int(safe_float(safe_get(archetype, "board_seat_preference", 1), 1))

    style = _likely_campaign_style(archetype, vulnerability, company)

    reasons: List[str] = []
    if mc_fit > 70:
        reasons.append(f"Company market cap aligns with archetype's preferred size range.")
    elif mc_fit < 40:
        reasons.append(f"Market cap is outside archetype's typical range, lowering fit.")
    if thesis_fit > 65:
        reasons.append(f"Vulnerability profile matches archetype's thesis weights.")
    if safe_get(company, "controlled_company_flag", False):
        reasons.append(f"Controlled company structure favors engagement-style archetypes only.")
    sector = str(safe_get(company, "sector", ""))
    if sector in {"Energy", "Materials", "Utilities"} and safe_float(safe_get(archetype, "esg_weight", 0), 0) > 50:
        reasons.append(f"Energy/utilities exposure and transition risk strengthen ESG-archetype fit.")
    if not reasons:
        reasons.append("Standard fit driven by composite scoring across cap, thesis, settlement.")

    return {
        "archetype_id": safe_get(archetype, "archetype_id", "A000"),
        "name": safe_get(archetype, "name", "Unknown Archetype"),
        "fit_score": fit_score,
        "likely_campaign_style": style,
        "likely_stake_pct": likely_stake,
        "likely_board_seats_requested": likely_seats,
        "why_this_activist_type": reasons,
    }


def rank_activist_archetypes(
    company,
    financials,
    vulnerability,
    fixability,
    archetypes):
    """Rank all archetypes by fit score descending."""
    if not archetypes:
        return []
    rows = []
    for a in archetypes:
        rows.append(score_activist_archetype_fit(
            company, financials, vulnerability, fixability, a))
    rows.sort(key=lambda r: r["fit_score"], reverse=True)
    return rows
