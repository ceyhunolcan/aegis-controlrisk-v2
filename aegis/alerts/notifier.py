# Alert formatting + delivery shims. The notifier doesn't actually send
# anything by default - it formats for stdout. Real deployments wire it
# to SMTP, Slack webhooks, Teams, etc. by passing a sender callback.
import json


def format_slack_blocks(alerts):
    """Render a list of alerts as Slack Block Kit JSON."""
    if not alerts:
        return None
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"Aegis: {len(alerts)} alert(s) fired"}},
        {"type": "divider"},
    ]
    severity_emoji = {
        "critical": "🚨", "high": "⚠️", "moderate": "🟡", "info": "ℹ️",
    }
    for a in alerts:
        e = severity_emoji.get(a["severity"], "•")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{e} *{a['severity'].upper()}* — "
                        f"*{a['company_name']}* ({a['company_id']})\n"
                        f"{a['message']}",
            },
        })
    return {"blocks": blocks}


def format_email_text(alerts, company_id=None):
    """Render alerts as a plain-text email body."""
    if not alerts:
        return "No alerts fired."
    lines = []
    header = "Aegis ControlRisk alert digest"
    if company_id:
        header += f" — {company_id}"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")
    for a in alerts:
        lines.append(f"[{a['severity'].upper()}] {a['rule_name']}")
        lines.append(f"  Company: {a['company_name']} ({a['company_id']})")
        lines.append(f"  Message: {a['message']}")
        lines.append(f"  Fired:   {a['fired_at_utc']}")
        lines.append("")
    lines.append("--")
    lines.append("This is not legal or investment advice.")
    return "\n".join(lines)


def format_digest_markdown(alerts):
    """Daily-digest format for a markdown report or web view."""
    if not alerts:
        return "_No alerts fired in this window._"

    severity_groups = {"critical": [], "high": [], "moderate": [], "info": []}
    for a in alerts:
        severity_groups.setdefault(a["severity"], []).append(a)

    parts = ["# Aegis Daily Alert Digest", ""]
    severity_emoji = {
        "critical": "🚨", "high": "⚠️", "moderate": "🟡", "info": "ℹ️",
    }

    for sev in ("critical", "high", "moderate", "info"):
        if not severity_groups[sev]:
            continue
        parts.append(f"## {severity_emoji[sev]} {sev.title()} "
                     f"({len(severity_groups[sev])})")
        parts.append("")
        for a in severity_groups[sev]:
            parts.append(f"- **{a['company_name']}** ({a['company_id']}): "
                         f"{a['message']}")
        parts.append("")
    return "\n".join(parts)


# Delivery hooks --------------------------------------------------------

def deliver(alerts, channel="stdout", sender=None, **kwargs):
    """
    Send alerts via a delivery channel.

    channel:
        "stdout"   - print text (default; useful for cron jobs piped to a log)
        "slack"    - return Slack Block Kit JSON; caller posts to webhook
        "email"    - return plain text email body; caller invokes SMTP
        "callback" - call `sender(alerts)` with the raw list

    All channels return the formatted payload so the caller can log it.
    """
    if not alerts:
        return None

    if channel == "stdout":
        out = format_email_text(alerts)
        print(out)
        return out

    if channel == "slack":
        return format_slack_blocks(alerts)

    if channel == "email":
        return format_email_text(alerts, **kwargs)

    if channel == "callback":
        if sender is None:
            raise ValueError("channel=callback requires sender=")
        return sender(alerts)

    raise ValueError(f"unknown channel: {channel}")
