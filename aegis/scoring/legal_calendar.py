# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Legal calendar + structural defense analysis. The "how feasible is this
# attack, even if everything else points to it" check. A controlled
# dual-class company can be the most vulnerable target in the model on
# every other axis and still register Moderate here because the activist
# literally can't win the vote.
#
# The output legal_feasibility_score combines:
#   - timing windows (nomination deadline, annual meeting)
#   - structural barriers (controlled co, dual class, classified board,
#     poison pill, advance notice bylaw)
#   - any signal of recent defensive amendments
#
# IMPORTANT: do not use this output as legal advice. It's a model, not
# a lawyer. The COMPLIANCE_NOTE is propagated downstream for that reason.
from datetime import date, datetime, timedelta
from typing import List

from ..utils.normalization import clamp, safe_float, safe_get
from config import COMPLIANCE_NOTE


def _parse_date(s):
    if s is None:
        return None
    if isinstance(s, date):
        return s
    if isinstance(s, datetime):
        return s.date()
    try:
        return datetime.fromisoformat(str(s)).date()
    except (ValueError, TypeError):
        try:
            return datetime.strptime(str(s), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None


def analyze_legal_calendar(
    company,
    as_of_date = None):
    """Analyze the governance/legal feasibility of a near-term campaign."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}
    if as_of_date is None:
        as_of_date = date.today()
    elif isinstance(as_of_date, str):
        parsed = _parse_date(as_of_date)
        as_of_date = parsed or date.today()
    elif isinstance(as_of_date, datetime):
        as_of_date = as_of_date.date()

    meeting = _parse_date(safe_get(company, "annual_meeting_date", None))
    nom_deadline = _parse_date(safe_get(company, "nomination_deadline", None))

    days_to_meeting = (meeting - as_of_date).days if meeting else None
    days_to_nom = (nom_deadline - as_of_date).days if nom_deadline else None

    deadline_missed = (days_to_nom is not None and days_to_nom < 0)

    # Structural flags
    classified = bool(safe_get(company, "classified_board", False))
    poison_pill = bool(safe_get(company, "has_poison_pill", False))
    controlled = bool(safe_get(company, "controlled_company_flag", False))
    dual_class = bool(safe_get(company, "dual_class_flag", False))
    majority_voting = bool(safe_get(company, "majority_voting_standard", True))
    ceo_chair = bool(safe_get(company, "ceo_chair_combined", False))

    # Feasibility score (higher = easier for an activist)
    feasibility = 70.0  # baseline
    warnings: List[str] = []

    if deadline_missed:
        feasibility -= 35
        warnings.append("Nomination deadline has passed for current meeting; next window 12-15 months out.")
    elif days_to_nom is not None and days_to_nom < 21:
        feasibility -= 8
        warnings.append(f"Nomination deadline only {days_to_nom} days away; tight window for due diligence.")
    elif days_to_nom is not None and 21 <= days_to_nom <= 90:
        feasibility += 5  # sweet spot

    if classified:
        feasibility -= 18
        warnings.append("Classified board: only a fraction of seats up each year; control takes multiple cycles.")
    if poison_pill:
        feasibility -= 10
        warnings.append("Poison pill in place: limits ability to accumulate above-threshold stake.")
    if controlled:
        feasibility -= 30
        warnings.append("Controlled company: a single holder can override a contested vote.")
    if dual_class and not controlled:
        feasibility -= 20
        warnings.append("Dual-class structure: insider super-voting dilutes activist vote power.")
    if not majority_voting:
        feasibility -= 8
        warnings.append("Plurality voting standard: incumbents can win with a single vote.")
    if not ceo_chair:
        feasibility += 4  # independent chair is mildly governance-friendly
    else:
        feasibility -= 3

    feasibility = clamp(feasibility)

    # Urgency score (higher = more urgent)
    urgency = 30.0
    if days_to_meeting is not None:
        if days_to_meeting < 0:
            urgency = 15
        elif days_to_meeting < 60:
            urgency = 95
        elif days_to_meeting < 120:
            urgency = 80
        elif days_to_meeting < 180:
            urgency = 55
        else:
            urgency = 35
    if deadline_missed:
        urgency = max(urgency, 20)  # 12-month planning urgency only

    urgency = clamp(urgency)

    summary_lines: List[str] = []
    if days_to_meeting is not None:
        summary_lines.append(f"Annual meeting in {days_to_meeting} days.")
    if days_to_nom is not None:
        if deadline_missed:
            summary_lines.append("Nomination deadline already passed.")
        else:
            summary_lines.append(f"Nomination deadline in {days_to_nom} days.")
    summary_lines.append(
        f"Structural posture: classified={classified}, poison_pill={poison_pill}, "
        f"controlled={controlled}, dual_class={dual_class}, majority_voting={majority_voting}."
    )

    return {
        "as_of_date": as_of_date.isoformat(),
        "annual_meeting_date": meeting.isoformat() if meeting else None,
        "nomination_deadline": nom_deadline.isoformat() if nom_deadline else None,
        "days_to_annual_meeting": days_to_meeting,
        "days_to_nomination_deadline": days_to_nom,
        "deadline_missed": deadline_missed,
        "legal_feasibility_score": round(feasibility, 1),
        "urgency_score": round(urgency, 1),
        "structural_flags": {
            "classified_board": classified,
            "poison_pill": poison_pill,
            "controlled_company": controlled,
            "dual_class": dual_class,
            "majority_voting": majority_voting,
            "ceo_chair_combined": ceo_chair,
        },
        "warnings": warnings,
        "calendar_summary": " ".join(summary_lines),
        "compliance_note": COMPLIANCE_NOTE,
    }
