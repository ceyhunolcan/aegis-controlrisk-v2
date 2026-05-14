# Fixability = "if an activist tried to fix this, how reasonable would it
# actually be?" High vulnerability + high fixability = the dream target.
# High vuln but low fix = a value trap (the activist gets in, can't move
# the needle, has to retreat). Seven components, root-cause clarity weighted
# heaviest because most failed campaigns trip on diagnosis, not execution.
from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100, weighted_score
)


WEIGHTS = {
    "root_cause_clarity": 0.20,
    "board_level_controllability": 0.18,
    "speed_of_value_realization": 0.18,
    "operational_levers_available": 0.16,
    "capital_allocation_levers_available": 0.14,
    "management_replaceability": 0.08,
    "execution_complexity_inverse": 0.06,
}


def _root_cause_clarity(fin):
    """Cleanly attributable underperformance -> higher fixability."""
    # Strong individual signals = clearer root cause
    mgn = abs(safe_float(safe_get(fin, "ebitda_margin_gap_vs_peer", 0.0), 0.0))
    roic = abs(safe_float(safe_get(fin, "roic_gap_vs_peer", 0.0), 0.0))
    capex = abs(safe_float(safe_get(fin, "capex_intensity_vs_peer", 0.0), 0.0))
    return clamp(0.4 * normalize_0_100(mgn, 0, 6) +
                 0.4 * normalize_0_100(roic, 0, 8) +
                 0.2 * normalize_0_100(capex, 0, 8))


def _board_level_controllability(company):
    """How much can a refreshed board actually move outcomes?"""
    score = 80.0
    if safe_get(company, "controlled_company_flag", False):
        score -= 40
    if safe_get(company, "dual_class_flag", False):
        score -= 25
    insider = safe_float(safe_get(company, "insider_ownership_pct", 0.0), 0.0)
    if insider >= 30:
        score -= 25
    elif insider >= 15:
        score -= 12
    if safe_get(company, "classified_board", False):
        score -= 10
    return clamp(score)


def _speed_of_value_realization(company, fin):
    """How fast can the thesis be cashed in?"""
    score = 60.0
    # Operational levers (margin) realize in 12-24 months
    if abs(safe_float(safe_get(fin, "ebitda_margin_gap_vs_peer", 0.0), 0.0)) > 3:
        score += 10
    # Capital return is fast
    if safe_float(safe_get(fin, "fcf_yield_vs_peer", 0.0), 0.0) > -2:
        score += 5
    # Classified board slows everything
    if safe_get(company, "classified_board", False):
        score -= 25
    # Strategic alternatives is slow
    sector = str(safe_get(company, "sector", ""))
    if sector in {"Healthcare"}:
        score -= 5  # regulatory drag
    if sector in {"Financials", "Banks"}:
        score -= 10  # regulatory drag
    return clamp(score)


def _operational_levers_available(fin):
    mgn = abs(safe_float(safe_get(fin, "ebitda_margin_gap_vs_peer", 0.0), 0.0))
    # 0pp gap -> 0; 6pp gap -> 100
    return clamp(normalize_0_100(mgn, 0, 6))


def _capital_allocation_levers_available(fin):
    capex = safe_float(safe_get(fin, "capex_intensity_vs_peer", 0.0), 0.0)
    mna = safe_float(safe_get(fin, "mna_writeoff_history_score", 50.0), 50.0)
    roic = abs(safe_float(safe_get(fin, "roic_gap_vs_peer", 0.0), 0.0))
    return clamp(0.35 * normalize_0_100(capex, -2, 8) +
                 0.35 * clamp(mna) +
                 0.30 * normalize_0_100(roic, 0, 8))


def _management_replaceability(company, fin):
    """In MVP this is a proxy from CEO/chair structure and dissent."""
    score = 55.0
    if safe_get(company, "ceo_chair_combined", False):
        score += 8
    sop = safe_float(safe_get(fin, "say_on_pay_support_pct", 90.0), 90.0)
    if sop < 75:
        score += 15
    elif sop < 85:
        score += 8
    dv = safe_float(safe_get(fin, "director_vote_support_avg_pct", 95.0), 95.0)
    if dv < 85:
        score += 10
    # If controlled, management is essentially un-replaceable
    if safe_get(company, "controlled_company_flag", False):
        score -= 30
    return clamp(score)


def _execution_complexity_inverse(company, fin):
    """Inverse: higher = simpler execution."""
    complexity = 40.0  # baseline
    if safe_float(safe_get(fin, "revenue_growth_vs_peer", 0.0), 0.0) < -3:
        complexity += 15
    if safe_float(safe_get(fin, "leverage_vs_peer", 0.0), 0.0) > 1.0:
        complexity += 12
    if safe_get(company, "sector", "") in {"Financials", "Banks", "Healthcare"}:
        complexity += 10
    inverse = 100.0 - clamp(complexity)
    return clamp(inverse)


def _classification(score):
    if score >= 75:
        return "High-conviction fixable target"
    if score >= 60:
        return "Fixable target"
    if score >= 40:
        return "Watchlist"
    return "Value trap"


def score_fixability(company, financials):
    """Compute the Fixability Score."""
    if company is None:
        company = {}
    if financials is None:
        financials = {}
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if hasattr(financials, "model_dump"):
        financials = financials.model_dump()

    components = {
        "root_cause_clarity": _root_cause_clarity(financials),
        "board_level_controllability": _board_level_controllability(company),
        "speed_of_value_realization": _speed_of_value_realization(company, financials),
        "operational_levers_available": _operational_levers_available(financials),
        "capital_allocation_levers_available": _capital_allocation_levers_available(financials),
        "management_replaceability": _management_replaceability(company, financials),
        "execution_complexity_inverse": _execution_complexity_inverse(company, financials),
    }
    score = weighted_score(components, WEIGHTS)
    classification = _classification(score)

    explanation = []
    sorted_comps = sorted(components.items(), key=lambda x: x[1], reverse=True)
    for k, v in sorted_comps[:4]:
        explanation.append(f"{k.replace('_', ' ').title()}: {v:.0f}/100")

    return {
        "score": score,
        "classification": classification,
        "components": components,
        "explanation": explanation,
    }
