# Active-trigger detection. Sweeps recent events + calendar pressure and
# produces a 0-100 score with a discrete urgency level. Real-world this
# would be wired to a news feed; here we read the events CSV.
#
# Time decay: events older than ~90 days get partial weight. A 13D filed
# yesterday is much louder than the same filing six months ago.
from datetime import date, datetime, timedelta
from typing import Dict, List

from ..utils.normalization import clamp, safe_float, safe_get


# How much each event-type contributes (additive, capped). Tuned roughly
# from observed historical campaign-trigger correlations.
TRIGGER_WEIGHTS = {
    "earnings_miss": 18,
    "guidance_cut": 22,
    "stock_drop": 18,
    "ceo_change": 25,
    "director_departure": 12,
    "failed_say_on_pay": 28,
    "activist_13d": 40,
    "activist_13g": 18,
    "ma_announcement": 15,
    "media_negative": 8,
    "regulatory_action": 18,
    "downgrade": 10,
}


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
        return None


def _decay(days_ago):
    """Recent events count more; older events decay."""
    if days_ago < 0:
        days_ago = 0
    if days_ago < 30:
        return 1.0
    if days_ago < 90:
        return 0.8
    if days_ago < 180:
        return 0.6
    if days_ago < 365:
        return 0.35
    return 0.15


def analyze_triggers(
    company,
    events,
    legal_calendar,
    as_of_date = None):
    """Detect active triggers and compute aggregate urgency."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}
    if as_of_date is None:
        as_of_date = date.today()
    elif isinstance(as_of_date, str):
        parsed = _parse_date(as_of_date)
        as_of_date = parsed or date.today()

    company_id = safe_get(company, "company_id", "")

    # Filter relevant events
    relevant: List[Dict] = []
    for e in events or []:
        ed = e.model_dump() if hasattr(e, "model_dump") else dict(e)
        if str(ed.get("company_id", "")) != str(company_id):
            continue
        relevant.append(ed)

    # Build active triggers
    triggers: List[Dict] = []
    total_score = 0.0
    for ed in relevant:
        d = _parse_date(ed.get("event_date"))
        if d is None:
            days_ago = 365
        else:
            days_ago = (as_of_date - d).days
        if days_ago > 540:
            continue  # too old to count as "active"
        ev_type = str(ed.get("event_type", "")).lower()
        sev = safe_float(ed.get("severity_score", 50), 50) / 100.0
        weight = TRIGGER_WEIGHTS.get(ev_type, 8)
        decay = _decay(days_ago)
        contribution = weight * sev * decay
        total_score += contribution
        triggers.append({
            "event_id": ed.get("event_id"),
            "event_type": ev_type,
            "event_date": ed.get("event_date"),
            "days_ago": days_ago,
            "severity_score": safe_float(ed.get("severity_score", 50), 50),
            "description": ed.get("description", ""),
            "contribution_to_trigger_score": round(contribution, 2),
        })

    # Calendar-based triggers
    days_to_meeting = legal_calendar.get("days_to_annual_meeting") if legal_calendar else None
    days_to_nom = legal_calendar.get("days_to_nomination_deadline") if legal_calendar else None

    if days_to_meeting is not None and 0 <= days_to_meeting <= 120:
        contribution = 12 * (1 - days_to_meeting / 120)
        total_score += contribution
        triggers.append({
            "event_id": "CAL_MEETING",
            "event_type": "meeting_approaching",
            "event_date": legal_calendar.get("annual_meeting_date"),
            "days_ago": -days_to_meeting,
            "severity_score": min(100, 50 + (120 - days_to_meeting) * 0.4),
            "description": f"Annual meeting in {days_to_meeting} days.",
            "contribution_to_trigger_score": round(contribution, 2),
        })
    if days_to_nom is not None and 0 <= days_to_nom <= 60:
        contribution = 15 * (1 - days_to_nom / 60)
        total_score += contribution
        triggers.append({
            "event_id": "CAL_NOM",
            "event_type": "nomination_approaching",
            "event_date": legal_calendar.get("nomination_deadline"),
            "days_ago": -days_to_nom,
            "severity_score": min(100, 60 + (60 - days_to_nom) * 0.5),
            "description": f"Nomination deadline in {days_to_nom} days.",
            "contribution_to_trigger_score": round(contribution, 2),
        })

    triggers.sort(key=lambda x: x["contribution_to_trigger_score"], reverse=True)
    trigger_score = clamp(total_score)

    if trigger_score >= 70:
        urgency = "Critical"
    elif trigger_score >= 50:
        urgency = "Elevated"
    elif trigger_score >= 30:
        urgency = "Moderate"
    else:
        urgency = "Low"

    actions: List[str] = []
    types = {t["event_type"] for t in triggers}
    if "activist_13d" in types:
        actions.append("Activate war room; align with proxy/legal counsel within 48 hours.")
    if "meeting_approaching" in types or "nomination_approaching" in types:
        actions.append("Lock down nomination response plan; prepare board engagement schedule.")
    if "failed_say_on_pay" in types:
        actions.append("Initiate compensation framework review with comp committee.")
    if "earnings_miss" in types or "guidance_cut" in types:
        actions.append("Refresh investor narrative pre-emptively; brief top 25 holders before next print.")
    if "ceo_change" in types:
        actions.append("Communicate transition plan and stability roadmap; engage governance team.")
    if not actions:
        actions.append("Maintain standard quarterly monitoring cadence.")

    summary = (
        f"Trigger score {trigger_score:.0f}/100 ({urgency}); "
        f"{len(triggers)} active signals."
    )

    return {
        "trigger_score": round(trigger_score, 1),
        "urgency_level": urgency,
        "active_triggers": triggers,
        "n_triggers": len(triggers),
        "recommended_monitoring_actions": actions,
        "summary": summary,
    }
