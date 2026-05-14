# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Director replaceability scoring. Nine components weighted to surface "which
# director is the activist most likely to target, and why" - tenure-excess +
# low-vote history + committee-chair exposure are the dominant signals in
# practice.
from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100, weighted_score
)


WEIGHTS = {
    "tenure_excess": 0.16,
    "accountability_gap": 0.15,
    "skills_gap": 0.14,
    "committee_chair_exposure": 0.12,
    "low_vote_history": 0.10,
    "overboarding": 0.10,
    "independence_gap": 0.09,
    "comp_oversight_exposure": 0.08,
    "esg_oversight_gap": 0.06,
}


def _tenure_excess(d):
    """Tenure > 10 years rises sharply."""
    t = safe_float(safe_get(d, "tenure_years", 0.0), 0.0)
    # 0-5 years: low risk; 5-10: moderate; >10: elevated; >15 high
    return normalize_0_100(t, min_value=4.0, max_value=18.0)


def _accountability_gap(d, company):
    """If company has weak governance and director is long-tenured insider, high gap."""
    score = 0.0
    if not bool(safe_get(d, "independent", True)):
        score += 35
    if bool(safe_get(company, "ceo_chair_combined", False)):
        score += 15
    if bool(safe_get(company, "classified_board", False)):
        score += 15
    if not bool(safe_get(company, "majority_voting_standard", True)):
        score += 20
    return clamp(score + 15)  # baseline floor


def _skills_gap(d, company):
    """Compare director skills against company sector needs."""
    sector = str(safe_get(company, "sector", "")).lower()
    sect_exp = safe_float(safe_get(d, "sector_expertise_score", 50), 50)
    cap_exp = safe_float(safe_get(d, "capital_allocation_expertise_score", 50), 50)
    tech_exp = safe_float(safe_get(d, "technology_expertise_score", 50), 50)
    climate_exp = safe_float(safe_get(d, "climate_transition_expertise_score", 50), 50)

    # Average expertise (inverse = gap)
    expertise = (sect_exp + cap_exp + tech_exp + climate_exp) / 4.0

    # Sector-specific penalties for missing expertise
    penalty = 0.0
    if "tech" in sector and tech_exp < 50:
        penalty += 10
    if "energy" in sector and climate_exp < 40:
        penalty += 15
    if cap_exp < 40:
        penalty += 8
    gap = clamp(100 - expertise) + penalty
    return clamp(gap)


def _committee_chair_exposure(d):
    """Chairs of audit/comp/governance committees are accountable."""
    is_chair = bool(safe_get(d, "is_committee_chair", False))
    roles = str(safe_get(d, "committee_roles", "")).lower()
    if not is_chair:
        if "audit" in roles or "compensation" in roles or "governance" in roles:
            return 50.0
        return 30.0
    if "audit" in roles:
        return 75.0
    if "compensation" in roles:
        return 80.0
    if "governance" in roles or "nominating" in roles:
        return 70.0
    return 65.0


def _low_vote_history(d):
    """Lower prior vote support = more replaceable."""
    pct = safe_float(safe_get(d, "prior_vote_support_pct", 90), 90)
    # 95%+ = very safe (low); 90-95 = mild; 80-90 = moderate; <80 = high
    return normalize_0_100(pct, min_value=98.0, max_value=70.0, inverse=False) if False else \
        normalize_0_100(100 - pct, min_value=2.0, max_value=30.0)


def _overboarding(d):
    """More than 2-3 other public boards is overboarding."""
    n = safe_float(safe_get(d, "other_public_boards", 0), 0)
    return normalize_0_100(n, min_value=1.0, max_value=5.0)


def _independence_gap(d):
    indep = bool(safe_get(d, "independent", True))
    return 80.0 if not indep else 25.0


def _comp_oversight_exposure(d, fin):
    """Director on comp committee at a company with low say-on-pay support."""
    on_comp = bool(safe_get(d, "compensation_oversight_flag", False)) or \
        "compensation" in str(safe_get(d, "committee_roles", "")).lower()
    sop = safe_float(safe_get(fin, "say_on_pay_support_pct", 90), 90)
    if not on_comp:
        return 25.0
    # Low SoP = high exposure
    return normalize_0_100(100 - sop, min_value=5.0, max_value=35.0)


def _esg_oversight_gap(d, company):
    """Lack of climate expertise at energy/industrial sector co."""
    sector = str(safe_get(company, "sector", "")).lower()
    climate = safe_float(safe_get(d, "climate_transition_expertise_score", 50), 50)
    if "energy" in sector or "industrial" in sector or "materials" in sector:
        return clamp(100 - climate)
    return clamp((100 - climate) * 0.4)


def _level(score):
    if score >= 70:
        return "High replaceability"
    if score >= 50:
        return "Moderate replaceability"
    if score >= 35:
        return "Low replaceability"
    return "Entrenched"


def _replacement_profile(d, company):
    sector = str(safe_get(company, "sector", "")).lower()
    roles = str(safe_get(d, "committee_roles", "")).lower()
    if "audit" in roles:
        return "Former CFO or audit partner with sector experience"
    if "compensation" in roles:
        return "Compensation expert / former CHRO with public company experience"
    if "governance" in roles or "nominating" in roles:
        return "Governance specialist / former GC at major public issuer"
    if "energy" in sector:
        return "Energy transition / climate operator with capital discipline track record"
    if "tech" in sector:
        return "Operator with technology platform scaling experience"
    if "industrial" in sector:
        return "Operational turnaround executive with margin improvement track record"
    return "Operating executive with capital allocation expertise and recent public board service"


def _top_reasons(components):
    out = []
    sorted_c = sorted(components.items(), key=lambda x: x[1], reverse=True)
    for k, v in sorted_c[:3]:
        out.append(f"{k.replace('_', ' ').title()}: {v:.0f}/100")
    return out


def _attack_angle(d, components, company):
    sector = str(safe_get(company, "sector", "")).lower()
    if components["low_vote_history"] > 50:
        return f"Below-peer prior vote support signals shareholder discontent with this director."
    if components["tenure_excess"] > 60:
        tenure = safe_float(safe_get(d, "tenure_years", 0), 0)
        return f"Long tenure ({tenure:.0f}y) raises independence and fresh-perspective concerns."
    if components["committee_chair_exposure"] > 60 and components["comp_oversight_exposure"] > 50:
        return "Chairs compensation committee at a company with weak say-on-pay support."
    if components["skills_gap"] > 60:
        return f"Skills profile mismatched to {sector or 'sector'} value drivers (e.g., transition, capital allocation)."
    if components["overboarding"] > 50:
        return "Multiple board commitments raise attention/availability concerns."
    if components["independence_gap"] > 50:
        return "Non-independent designation invites targeted activist scrutiny."
    return "Composite of moderate-tenure, weak skills mix, and committee accountability."


def score_director_replaceability(
    director,
    company,
    financials):
    """Score a single director's replaceability."""
    if hasattr(director, "model_dump"):
        director = director.model_dump()
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if hasattr(financials, "model_dump"):
        financials = financials.model_dump()
    if financials is None:
        financials = {}
    if company is None:
        company = {}

    components = {
        "tenure_excess": _tenure_excess(director),
        "accountability_gap": _accountability_gap(director, company),
        "skills_gap": _skills_gap(director, company),
        "committee_chair_exposure": _committee_chair_exposure(director),
        "low_vote_history": _low_vote_history(director),
        "overboarding": _overboarding(director),
        "independence_gap": _independence_gap(director),
        "comp_oversight_exposure": _comp_oversight_exposure(director, financials),
        "esg_oversight_gap": _esg_oversight_gap(director, company),
    }
    score = weighted_score(components, WEIGHTS)
    level = _level(score)

    return {
        "director_id": safe_get(director, "director_id", ""),
        "name": safe_get(director, "name", ""),
        "score": round(score, 1),
        "risk_level": level,
        "components": components,
        "top_reasons": _top_reasons(components),
        "best_activist_attack_angle": _attack_angle(director, components, company),
        "recommended_replacement_profile": _replacement_profile(director, company),
        "tenure_years": safe_float(safe_get(director, "tenure_years", 0), 0),
        "independent": bool(safe_get(director, "independent", True)),
        "committee_roles": safe_get(director, "committee_roles", ""),
        "is_committee_chair": bool(safe_get(director, "is_committee_chair", False)),
        "prior_vote_support_pct": safe_float(safe_get(director, "prior_vote_support_pct", 90), 90),
    }


def score_all_directors(
    directors,
    company,
    financials):
    """Score all directors for a company; return sorted desc by replaceability."""
    if not directors:
        return []
    rows = [score_director_replaceability(d, company, financials) for d in directors]
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
