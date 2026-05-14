# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Management defense readiness. Mirror of vulnerability - same picture from
# the other side of the table. Evidence rebuttability is the largest weight
# because in proxy fights the most damaging claims are ones with paper
# trails the company can't credibly walk back.
from typing import List

from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100, weighted_score
)


WEIGHTS = {
    "evidence_rebuttability": 0.20,
    "operating_momentum": 0.15,
    "board_credibility": 0.15,
    "shareholder_trust": 0.15,
    "strategic_clarity": 0.10,
    "proxy_advisor_appeal": 0.10,
    "media_narrative_control": 0.10,
    "legal_protection": 0.05,
}


def _evidence_rebuttability(claim_graph, primary_thesis):
    """Higher = more of the activist's claims are rebuttable."""
    claims = claim_graph.get("claims", []) if claim_graph else []
    if not claims:
        return 50.0
    avg_rebut = sum(safe_float(c.get("rebuttability", 50), 50) for c in claims) / max(len(claims), 1)
    return clamp(avg_rebut)


def _operating_momentum(fin):
    tsr1 = safe_float(safe_get(fin, "tsr_1y_vs_peer", 0), 0)
    momentum = safe_float(safe_get(fin, "recent_stock_momentum_score", 50), 50)
    rev = safe_float(safe_get(fin, "revenue_growth_vs_peer", 0), 0)
    s_tsr = normalize_0_100(tsr1, min_value=-20.0, max_value=20.0)
    s_rev = normalize_0_100(rev, min_value=-5.0, max_value=10.0)
    return clamp(0.4 * s_tsr + 0.4 * momentum + 0.2 * s_rev)


def _board_credibility(company, director_scores):
    """If board has many high-replaceability directors, credibility is low."""
    if not director_scores:
        base = 60.0
    else:
        avg_replace = sum(safe_float(d.get("score", 50), 50) for d in director_scores) / max(len(director_scores), 1)
        base = clamp(100 - avg_replace)
    if bool(safe_get(company, "ceo_chair_combined", False)):
        base -= 6
    if bool(safe_get(company, "classified_board", False)):
        base -= 3
    return clamp(base)


def _shareholder_trust(fin):
    sop = safe_float(safe_get(fin, "say_on_pay_support_pct", 90), 90)
    dir_avg = safe_float(safe_get(fin, "director_vote_support_avg_pct", 92), 92)
    return clamp(0.5 * normalize_0_100(sop, 60, 99) + 0.5 * normalize_0_100(dir_avg, 70, 99))


def _strategic_clarity(fin, company):
    """Synthetic: write-off history + guidance miss + spin/M&A confusion."""
    mna = safe_float(safe_get(fin, "mna_writeoff_history_score", 50), 50)
    guid = safe_float(safe_get(fin, "guidance_miss_frequency", 0.2), 0.2)
    score = 100 - 0.4 * mna - 60 * guid
    return clamp(score)


def _proxy_advisor_appeal(pa_view):
    """High P(mgmt full slate) means PA appeal is good."""
    p_full = safe_float(safe_get(pa_view, "p_support_management_full_slate", 0.6), 0.6)
    return clamp(p_full * 100.0)


def _media_narrative_control(company, fin, vulnerability):
    """Strong financial performance + low governance flags = better narrative control."""
    v = safe_float(safe_get(vulnerability, "score", 50), 50)
    return clamp(100 - v)


def _legal_protection(company):
    """Poison pill + classified board + controlled structure all aid defense."""
    score = 30.0
    if bool(safe_get(company, "has_poison_pill", False)):
        score += 25
    if bool(safe_get(company, "classified_board", False)):
        score += 25
    if bool(safe_get(company, "controlled_company_flag", False)):
        score += 35
    if bool(safe_get(company, "dual_class_flag", False)):
        score += 25
    if not bool(safe_get(company, "majority_voting_standard", True)):
        score += 10
    return clamp(score)


def _level(score):
    if score >= 75:
        return "Strong defense"
    if score >= 55:
        return "Moderate defense"
    if score >= 35:
        return "Weak defense"
    return "Critical defensive position"


def _response_strategy(components, level):
    weak = sorted(components.items(), key=lambda x: x[1])[:2]
    strong = sorted(components.items(), key=lambda x: x[1], reverse=True)[:2]
    return (
        f"Defense posture: {level}. "
        f"Lean into strengths: {', '.join(k.replace('_', ' ') for k, _ in strong)}. "
        f"Pre-empt weaknesses: {', '.join(k.replace('_', ' ') for k, _ in weak)}. "
        f"Run engagement-first track; reserve litigation only if structural protections are tested."
    )


def _rebuttal_memo(
    components, primary_thesis,
    claim_graph, company):
    lines: List[str] = []
    cname = safe_get(company, "name", "the Company")
    lines.append(f"MEMORANDUM — Defense Rebuttal Outline for {cname}")
    lines.append("")
    lines.append("1. Operating Momentum")
    lines.append(f"   - Internal score {components['operating_momentum']:.0f}/100.")
    lines.append("   - Lead with most recent quarterly outperformance vs. plan and recent strategic milestones.")
    lines.append("")
    lines.append("2. Capital Allocation Record")
    lines.append("   - Show 5-year cumulative capital return (buyback + dividend) and ROIC trajectory.")
    lines.append("   - Pre-empt any M&A write-off line item with retrospective rationale and lessons learned.")
    lines.append("")
    lines.append("3. Board Refresh and Skills")
    lines.append(f"   - Internal board-credibility score {components['board_credibility']:.0f}/100.")
    lines.append("   - Highlight tenure mix, recent additions, and skills-matrix coverage of strategic priorities.")
    lines.append("")
    lines.append("4. Governance Posture")
    lines.append(f"   - Internal legal-protection score {components['legal_protection']:.0f}/100.")
    lines.append("   - Communicate governance roadmap (declassification, majority voting) where credible.")
    lines.append("")
    lines.append("5. Proxy Advisor Engagement")
    lines.append(f"   - PA appeal {components['proxy_advisor_appeal']:.0f}/100.")
    lines.append("   - Schedule pre-meeting briefings with ISS / Glass Lewis governance and compensation teams.")
    lines.append("")
    lines.append("6. Direct Rebuttal of Activist Claims")
    claims = claim_graph.get("most_rebuttable_claims", []) if claim_graph else []
    if claims:
        for c in claims[:3]:
            lines.append(f"   - {c.get('claim_text', '')} (rebuttability {c.get('rebuttability', 0):.0f}/100).")
    else:
        lines.append("   - Address top 3 anticipated activist claims with quantitative counter-evidence.")
    lines.append("")
    lines.append("This is not legal advice. For execution, retain proxy solicitation and legal counsel.")
    return "\n".join(lines)


def simulate_management_defense(
    company,
    financials,
    primary_thesis,
    claim_graph,
    director_scores,
    pa_view,
    vulnerability):
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if hasattr(financials, "model_dump"):
        financials = financials.model_dump()
    if company is None:
        company = {}
    if financials is None:
        financials = {}

    components = {
        "evidence_rebuttability": _evidence_rebuttability(claim_graph or {}, primary_thesis or {}),
        "operating_momentum": _operating_momentum(financials),
        "board_credibility": _board_credibility(company, director_scores or []),
        "shareholder_trust": _shareholder_trust(financials),
        "strategic_clarity": _strategic_clarity(financials, company),
        "proxy_advisor_appeal": _proxy_advisor_appeal(pa_view or {}),
        "media_narrative_control": _media_narrative_control(company, financials, vulnerability or {}),
        "legal_protection": _legal_protection(company),
    }
    score = weighted_score(components, WEIGHTS)
    level = _level(score)

    sorted_strong = sorted(components.items(), key=lambda x: x[1], reverse=True)
    sorted_weak = sorted(components.items(), key=lambda x: x[1])

    strongest = [{"name": k.replace("_", " ").title(), "score": round(v, 1)} for k, v in sorted_strong[:3]]
    weakest = [{"name": k.replace("_", " ").title(), "score": round(v, 1)} for k, v in sorted_weak[:3]]

    return {
        "defense_strength_score": round(score, 1),
        "defense_level": level,
        "components": components,
        "strongest_defenses": strongest,
        "weakest_defenses": weakest,
        "recommended_response_strategy": _response_strategy(components, level),
        "management_rebuttal_memo": _rebuttal_memo(components, primary_thesis or {}, claim_graph or {}, company),
    }
