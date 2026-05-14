# Layer-1 executive view. Single landing page, designed to answer one
# question for a director or principal scanning their morning briefing:
# "what do I need to know about this company right now?"
#
# Three sections only: a verdict line, the three reasons, and the next
# action. No analyst content. If the user wants more, they click into
# Layer 2 or 3.
#
# This is a pure rendering module - it takes an analysis dict and returns
# either a Streamlit-renderable structure or a markdown blob, depending on
# what the caller wants.


def executive_verdict(analysis):
    """One-paragraph verdict. The thing you'd read on your phone in 30 sec."""
    company = analysis.get("company") or {}
    final = analysis.get("final_score") or {}
    sim = analysis.get("simulation") or {}
    legal = analysis.get("legal") or {}
    worst = analysis.get("worst_case") or {}

    name = company.get("name", "the company")
    level = final.get("final_risk_level", "—")
    p_event = float(final.get("activism_event_probability_12m") or 0)
    p_win = float(sim.get("p_activist_wins_1_plus") or 0)
    days_to_meeting = legal.get("days_to_annual_meeting")

    urgency = ""
    if isinstance(days_to_meeting, (int, float)) and 0 <= days_to_meeting <= 120:
        urgency = (f" The annual meeting is in {int(days_to_meeting)} days, "
                   f"which compresses the response window.")

    # Add the worst-case message if we have it; this is a distinguishing
    # feature - most tools never expose worst-plausible-case numbers.
    worst_note = ""
    if worst.get("p95_seats_lost") is not None:
        p95 = worst["p95_seats_lost"]
        if p95 >= 1:
            worst_note = (f" Worst-plausible-case (95th percentile): "
                          f"{p95:.0f} seat(s) lost.")

    return (
        f"**{name}** is rated **{level}** for activism risk. "
        f"Modeled 12-month event probability is **{p_event * 100:.0f}%**; "
        f"if a campaign launches, P(activist wins ≥1 seat) is "
        f"**{p_win * 100:.0f}%**.{urgency}{worst_note}"
    )


def top_three_reasons(analysis, n=3):
    """The three most important things driving the risk level today.

    Pulled from the vulnerability explanation list, then trimmed and
    re-phrased to read like prose, not score components.
    """
    vuln = analysis.get("vulnerability") or {}
    primary = analysis.get("primary_thesis") or {}
    triggers = analysis.get("triggers") or {}

    reasons = []

    # First reason: the dominant thesis driver (most actionable framing)
    if primary.get("name"):
        reasons.append(
            f"The most likely activist play is **{primary['name']}**, "
            f"with an estimated upside narrative of "
            f"**{primary.get('estimated_upside_range', 'meaningful')}**."
        )

    # Second + third: top components of vulnerability
    explanation = vuln.get("explanation") or []
    for line in explanation[: n - len(reasons)]:
        reasons.append(line)

    # If we still need more, look at active triggers
    if len(reasons) < n and triggers.get("active_triggers"):
        for t in triggers["active_triggers"][: n - len(reasons)]:
            label = t.get("trigger_type", "—") if isinstance(t, dict) else str(t)
            desc = t.get("description", "") if isinstance(t, dict) else ""
            reasons.append(f"Active trigger: **{label}**. {desc}".strip())

    return reasons[:n]


def recommended_next_action(analysis):
    """One sentence: what should the board do this week?

    Pulled from settlement_game.recommended_path + the top of the defense
    package's 90-day plan."""
    settlement = analysis.get("settlement") or {}
    defense_pkg = analysis.get("defense_package") or {}
    legal = analysis.get("legal") or {}

    path = settlement.get("recommended_path", "")
    rec_actions = defense_pkg.get("recommended_actions") or []
    top_action = rec_actions[0].get("action_name", "") if rec_actions else ""

    nom_days = legal.get("days_to_nomination_deadline")
    if isinstance(nom_days, (int, float)) and 0 <= nom_days <= 45:
        return (f"**Immediate action this week**: with nomination deadline in "
                f"{int(nom_days)} days, the highest-leverage move is "
                f"{top_action.lower() if top_action else 'pre-empting the activist with a board refresh'}.")

    if path and top_action:
        return (f"**Recommended path:** {path}. The top action in the modeled "
                f"defense package is **{top_action}**.")

    if top_action:
        return f"**Top recommended action**: {top_action}."

    return "**Status**: no critical actions required this week. Continue monitoring."


def render_executive_view(analysis):
    """Compose all three sections into a markdown deliverable."""
    return "\n\n".join([
        "## Verdict",
        executive_verdict(analysis),
        "## Top 3 reasons",
        "\n".join(f"{i+1}. {r}" for i, r in enumerate(top_three_reasons(analysis))),
        "## What to do this week",
        recommended_next_action(analysis),
    ])
