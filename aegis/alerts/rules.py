# Alert engine. Compares two snapshots and decides whether anything material
# changed. Material is defined by configurable rules - e.g. risk level
# crosses a boundary, an active trigger fires, the nomination deadline is
# inside 30 days.
#
# The engine is delivery-agnostic. It returns a list of Alert dicts that a
# downstream notifier can send via email / Slack / Teams / webhook.
from datetime import datetime, timezone


# Each rule is (name, severity, predicate, message_template). Predicate
# takes (old_analysis, new_analysis) and returns truthy when the rule fires.
# Severity: "critical" / "high" / "moderate" / "info".

def _safe_get(d, *path, default=None):
    cur = d
    for k in path:
        if cur is None or not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _risk_level_changed(old, new):
    o = _safe_get(old, "final_score", "final_risk_level")
    n = _safe_get(new, "final_score", "final_risk_level")
    return o != n and o is not None and n is not None


def _risk_escalated(old, new):
    order = {"Low": 0, "Moderate": 1, "High": 2, "Critical": 3}
    o = order.get(_safe_get(old, "final_score", "final_risk_level"), -1)
    n = order.get(_safe_get(new, "final_score", "final_risk_level"), -1)
    return n > o >= 0


def _risk_score_jump(old, new, threshold=10):
    o = _safe_get(old, "final_score", "activism_risk_score_0_100")
    n = _safe_get(new, "final_score", "activism_risk_score_0_100")
    if o is None or n is None:
        return False
    try:
        return abs(float(n) - float(o)) >= threshold
    except (TypeError, ValueError):
        return False


def _nomination_deadline_imminent(_, new, days_threshold=30):
    d = _safe_get(new, "legal", "days_to_nomination_deadline")
    if d is None:
        return False
    try:
        d = int(d)
    except (TypeError, ValueError):
        return False
    return 0 <= d <= days_threshold


def _new_active_trigger(old, new):
    old_count = _safe_get(old, "triggers", "n_triggers", default=0)
    new_count = _safe_get(new, "triggers", "n_triggers", default=0)
    try:
        return int(new_count) > int(old_count)
    except (TypeError, ValueError):
        return False


def _p_activist_wins_high(_, new, threshold=0.50):
    p = _safe_get(new, "simulation", "p_activist_wins_1_plus")
    if p is None:
        return False
    try:
        return float(p) >= threshold
    except (TypeError, ValueError):
        return False


def _settlement_pressure_high(_, new, threshold=70):
    s = _safe_get(new, "final_score", "settlement_pressure_index")
    if s is None:
        return False
    try:
        return float(s) >= threshold
    except (TypeError, ValueError):
        return False


# Rule registry
RULES = [
    {
        "name": "risk_level_escalated",
        "severity": "critical",
        "predicate": _risk_escalated,
        "message": "Risk level escalated from {old_risk} to {new_risk}.",
    },
    {
        "name": "risk_level_changed",
        "severity": "high",
        "predicate": lambda o, n: _risk_level_changed(o, n) and not _risk_escalated(o, n),
        "message": "Risk level changed from {old_risk} to {new_risk}.",
    },
    {
        "name": "risk_score_jump",
        "severity": "high",
        "predicate": _risk_score_jump,
        "message": "Risk score moved ≥10 points: {old_score} → {new_score}.",
    },
    {
        "name": "nomination_deadline_imminent",
        "severity": "high",
        "predicate": _nomination_deadline_imminent,
        "message": "Nomination deadline is in {days_to_deadline} days.",
    },
    {
        "name": "new_active_trigger",
        "severity": "moderate",
        "predicate": _new_active_trigger,
        "message": "New active trigger(s) detected. Trigger count: "
                   "{trigger_count} (was {old_trigger_count}).",
    },
    {
        "name": "activist_likely_to_win",
        "severity": "critical",
        "predicate": _p_activist_wins_high,
        "message": "Modeled P(activist wins ≥1 seat) is {p_win:.0%}.",
    },
    {
        "name": "high_settlement_pressure",
        "severity": "high",
        "predicate": _settlement_pressure_high,
        "message": "Settlement pressure index at {settlement_pressure:.0f}/100.",
    },
]


def _format_message(template, old, new):
    """Fill template placeholders from the analyses."""
    ctx = {
        "old_risk": _safe_get(old, "final_score", "final_risk_level", default="—"),
        "new_risk": _safe_get(new, "final_score", "final_risk_level", default="—"),
        "old_score": _safe_get(old, "final_score", "activism_risk_score_0_100", default="—"),
        "new_score": _safe_get(new, "final_score", "activism_risk_score_0_100", default="—"),
        "days_to_deadline": _safe_get(new, "legal", "days_to_nomination_deadline", default="—"),
        "trigger_count": _safe_get(new, "triggers", "n_triggers", default=0),
        "old_trigger_count": _safe_get(old, "triggers", "n_triggers", default=0),
        "p_win": float(_safe_get(new, "simulation", "p_activist_wins_1_plus", default=0) or 0),
        "settlement_pressure": float(_safe_get(new, "final_score", "settlement_pressure_index", default=0) or 0),
    }
    try:
        return template.format(**ctx)
    except (KeyError, ValueError):
        return template


def check_alerts(old_analysis, new_analysis, rules=None):
    """
    Compare two analyses and return a list of fired alerts.

    old_analysis can be None (first run, no baseline). Rules that need a
    baseline are skipped in that case.
    """
    rules = rules or RULES
    old = old_analysis or {}
    new = new_analysis or {}
    company_id = new.get("company_id") or "UNKNOWN"
    company_name = (new.get("company") or {}).get("name", company_id)

    alerts = []
    for rule in rules:
        try:
            fired = rule["predicate"](old, new)
        except Exception:
            continue
        if not fired:
            continue
        alerts.append({
            "rule_name": rule["name"],
            "severity": rule["severity"],
            "company_id": company_id,
            "company_name": company_name,
            "message": _format_message(rule["message"], old, new),
            "fired_at_utc": datetime.now(timezone.utc).isoformat(),
        })
    return alerts


def filter_by_severity(alerts, min_severity="moderate"):
    order = {"info": 0, "moderate": 1, "high": 2, "critical": 3}
    threshold = order.get(min_severity, 0)
    return [a for a in alerts if order.get(a["severity"], 0) >= threshold]
