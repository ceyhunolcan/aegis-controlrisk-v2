# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Shadow report for ISS / Glass Lewis. We don't have access to their actual
# models obviously, but we can approximate the published rubrics: governance
# weight, performance vs peers, board composition concerns, and pay
# alignment. Outputs are probabilities, not endorsements - the dashboard
# surfaces these as "P(PA supports X)".
#
# Calibration is wide on purpose - if you find yourself believing a
# probability here to 1 percentage point, you're overfitting the model.
from typing import List

from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100, probability_clamp
)


def _governance_score_for_pa(company, fin):
    """Synthesize a 0-100 governance "concern" score from PA perspective."""
    score = 50.0
    if bool(safe_get(company, "classified_board", False)):
        score += 12
    if bool(safe_get(company, "ceo_chair_combined", False)):
        score += 8
    if not bool(safe_get(company, "majority_voting_standard", True)):
        score += 10
    if bool(safe_get(company, "has_poison_pill", False)):
        score += 8
    if bool(safe_get(company, "dual_class_flag", False)):
        score += 15
    if bool(safe_get(company, "controlled_company_flag", False)):
        score += 10
    sop = safe_float(safe_get(fin, "say_on_pay_support_pct", 90), 90)
    if sop < 75:
        score += 18
    elif sop < 85:
        score += 8
    return clamp(score)


def simulate_proxy_advisor_view(
    company,
    financials,
    primary_thesis,
    director_scores,
    vulnerability,
    fixability):
    """Estimate proxy advisor (ISS/Glass Lewis) recommendation probabilities."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if hasattr(financials, "model_dump"):
        financials = financials.model_dump()
    if company is None:
        company = {}
    if financials is None:
        financials = {}

    pa_gov = _governance_score_for_pa(company, financials)
    v_score = safe_float(safe_get(vulnerability, "score", 50), 50)
    f_score = safe_float(safe_get(fixability, "score", 50), 50)
    thesis_score = safe_float(safe_get(primary_thesis, "score", 50), 50)
    pa_compat = safe_float(safe_get(primary_thesis, "proxy_advisor_compatibility", 50), 50)
    sop = safe_float(safe_get(financials, "say_on_pay_support_pct", 90), 90)

    # Probability PA supports full mgmt slate decreases when governance concern + vulnerability rise
    p_mgmt_full = clamp(
        85 - 0.30 * pa_gov - 0.30 * v_score - 0.15 * pa_compat + 0.10 * (100 - thesis_score) + 0.10 * f_score, 5, 95
    ) / 100.0

    # P(support 1+ activist nominee)
    p_one = clamp(
        15 + 0.30 * v_score + 0.20 * pa_compat + 0.20 * pa_gov - 0.15 * f_score, 5, 90
    ) / 100.0

    # P(support 2+)
    p_two = clamp(
        5 + 0.25 * v_score + 0.20 * pa_compat + 0.15 * pa_gov - 0.20 * f_score, 0, 70
    ) / 100.0

    # Renormalize: at most one of these is true and they should be loosely consistent
    # but they aren't strictly mutually exclusive — they represent recommendations.

    # Against pay - tied to SoP support
    p_against_pay = clamp(
        100 - sop + 0.10 * pa_gov - 30, 2, 80
    ) / 100.0

    # Against specific director (highest replaceability) probability
    if director_scores:
        top = director_scores[0]
        top_score = safe_float(top.get("score", 50), 50)
        p_against_dir = clamp(top_score * 0.6 + 5, 5, 90) / 100.0
        top_dir_name = top.get("name", "")
    else:
        p_against_dir = 0.20
        top_dir_name = ""

    key_drivers: List[str] = []
    if pa_gov > 60:
        key_drivers.append(f"Elevated governance concern score ({pa_gov:.0f}/100): structural / oversight features.")
    if sop < 80:
        key_drivers.append(f"Below-peer say-on-pay support ({sop:.0f}%): comp committee under scrutiny.")
    if v_score > 60:
        key_drivers.append(f"Strong evidence-based vulnerability ({v_score:.0f}/100) supports change case.")
    if pa_compat > 70:
        key_drivers.append("Activist thesis aligns with PA frameworks (board accountability, capital allocation).")
    if not key_drivers:
        key_drivers.append("Governance posture is moderate; PA outcome likely depends on contested-case specifics.")

    preemptive_steps: List[str] = []
    if pa_gov > 55:
        preemptive_steps.append("Engage ISS/Glass Lewis governance teams 6-9 months ahead of meeting on governance reforms.")
    if sop < 80:
        preemptive_steps.append("Pre-empt with compensation framework reset; engage top 25 shareholders pre-meeting.")
    if bool(safe_get(company, "classified_board", False)):
        preemptive_steps.append("Telegraph board declassification plan to defuse a governance-on-governance attack.")
    if bool(safe_get(company, "ceo_chair_combined", False)):
        preemptive_steps.append("Consider lead independent director enhancement / chair separation roadmap.")
    if p_against_dir > 0.50 and top_dir_name:
        preemptive_steps.append(
            f"Pre-empt PA against-rec on {top_dir_name}: address tenure/skills mix proactively."
        )
    if not preemptive_steps:
        preemptive_steps.append("Maintain consistent engagement cadence; no acute PA risk identified.")

    summary = (
        f"PA shadow: P(support full mgmt slate)={p_mgmt_full:.0%}; "
        f"P(support 1+ activist nominee)={p_one:.0%}; "
        f"P(against pay)={p_against_pay:.0%}."
    )

    return {
        "p_support_management_full_slate": round(probability_clamp(p_mgmt_full), 3),
        "p_support_one_activist_nominee": round(probability_clamp(p_one), 3),
        "p_support_two_plus_activist_nominees": round(probability_clamp(p_two), 3),
        "p_recommend_against_pay": round(probability_clamp(p_against_pay), 3),
        "p_recommend_against_specific_director": round(probability_clamp(p_against_dir), 3),
        "specific_director_at_risk": top_dir_name,
        "pa_governance_concern_score": round(pa_gov, 1),
        "key_drivers": key_drivers,
        "recommended_preemptive_steps": preemptive_steps,
        "summary": summary,
    }
