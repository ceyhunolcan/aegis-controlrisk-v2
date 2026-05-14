# War-room narrative outputs - the stuff IR/legal/comms actually use in
# the first 72 hours when a 13D drops. Each function returns either a
# markdown string or a list of dicts (for board Q&A). generate_war_room_outputs
# bundles them all.
from config import COMPLIANCE_NOTE


def _pct(x, default="–"):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return f"{v * 100:.0f}%" if v <= 1.0 else f"{v:.0f}%"


def generate_red_team_attack(analysis):
    """If I were the activist, here's the case I'd make."""
    company = analysis.get("company") or {}
    name, ticker = company.get("name", "the Company"), company.get("ticker", "—")
    primary = analysis.get("primary_thesis") or {}
    dna = analysis.get("activist_dna_top") or {}
    claim_attack = analysis.get("claim_attack_table") or []
    director_scores = analysis.get("director_scores") or []

    out = [
        f"# Red Team: How an Activist Will Attack {name} ({ticker})",
        "",
        f"**Likely attacker profile:** {dna.get('name', 'Mainstream constructivist')} "
        f"— campaign style: *{dna.get('likely_campaign_style', '—')}*; "
        f"likely stake ~{dna.get('likely_stake_pct', '–')}%; "
        f"likely seats requested: {dna.get('likely_board_seats_requested', '–')}",
        "",
        "## The headline",
        "",
        f"**\"{primary.get('name', 'Value-Realization Plan')}\"** "
        f"— power score {primary.get('score', '–')}/100.",
        "",
        "## The 60-second pitch to LPs",
        "",
        primary.get("activist_attack_memo", "—"),
        "",
        "## The strongest claims they will use",
        "",
    ]
    for row in claim_attack[:5]:
        out.append(f"- **{row.get('claim', '—')}** "
                   f"(power {row.get('claim_power_score', '–')}, "
                   f"resonance with shareholders: {row.get('shareholder_resonance', '–')})")
        if row.get("supporting_evidence"):
            out.append(f"  - Evidence: {row.get('supporting_evidence')}")

    out += ["", "## The directors they will target", ""]
    high_risk = sorted(
        [d for d in director_scores if d.get("risk_level") in ("Critical", "High")],
        key=lambda d: -float(d.get("score", 0) or 0),
    )[:3]
    if high_risk:
        for d in high_risk:
            out.append(f"- **{d.get('name', '—')}** "
                       f"(score {d.get('score', '–')}/100, risk {d.get('risk_level', '—')}): "
                       f"{d.get('best_activist_attack_angle', '—')}")
    else:
        out.append("- (No clearly vulnerable directors identified; activist will likely "
                   "propose a refresh rather than name specific replacements.)")

    settlement = analysis.get("settlement") or {}
    out += [
        "",
        "## Their settlement floor",
        "",
        f"Likely settlement floor: {settlement.get('best_option', {}).get('option_name', '—')}.",
        "",
        "---",
        f"*{COMPLIANCE_NOTE}*",
    ]
    return "\n".join(out)


def generate_blue_team_defense(analysis):
    """Mirror image - management's strongest defensible posture."""
    company = analysis.get("company") or {}
    name = company.get("name", "the Company")
    defense = analysis.get("defense") or {}
    claim_defense = analysis.get("claim_defense_table") or []
    legal = analysis.get("legal") or {}

    out = [
        f"# Blue Team: Management's Strongest Defense for {name}",
        "",
        f"**Current defense strength:** {defense.get('defense_strength_score', '–')}/100 "
        f"— {defense.get('defense_level', '—')}",
        "",
        "## Core narrative",
        "",
        defense.get("management_rebuttal_memo", "—"),
        "",
        "## Strongest defense pillars",
        "",
    ]
    for s in (defense.get("strongest_defenses") or [])[:5]:
        if isinstance(s, dict):
            out.append(f"- **{s.get('label', s.get('name', '—'))}** "
                       f"— {s.get('explanation', '')}")
        else:
            out.append(f"- {s}")

    out += ["", "## Weak flanks to harden", ""]
    for w in (defense.get("weakest_defenses") or [])[:5]:
        if isinstance(w, dict):
            out.append(f"- **{w.get('label', w.get('name', '—'))}** "
                       f"— {w.get('explanation', '')}")
        else:
            out.append(f"- {w}")

    out += ["", "## Claim-by-claim rebuttals", ""]
    for row in claim_defense[:6]:
        out.append(f"- **Claim:** {row.get('claim', '—')}")
        out.append(f"  - **Rebuttal:** "
                   f"{row.get('management_defense', row.get('defense_response', '—'))}")

    out += ["", "## Structural defenses available", ""]
    flags = legal.get("structural_flags") or []
    flag_lines = []
    if isinstance(flags, dict):
        for k, v in flags.items():
            if v in (None, False, "", 0):
                continue
            flag_lines.append(f"- {k}: {v}")
    elif isinstance(flags, list):
        for f in flags[:6]:
            flag_lines.append(f"- {f}")
    if flag_lines:
        out.extend(flag_lines[:6])
    else:
        out.append("- (No special structural defenses; rely on operating "
                   "and communication response.)")

    out += ["", "---", f"*{COMPLIANCE_NOTE}*"]
    return "\n".join(out)


def _top_actions(defense_pkg, n=3):
    actions = (defense_pkg or {}).get("recommended_actions") or []
    if not actions:
        return "(No specific actions ranked.)"
    return "; ".join(
        f"{a.get('action_id', '')}: {a.get('action_name', '—')}" for a in actions[:n]
    )


def generate_board_qa(analysis):
    """The questions a board will actually ask. Answered in 1-3 sentences each."""
    final = analysis.get("final_score") or {}
    sim = analysis.get("simulation") or {}
    coalition = analysis.get("coalition") or {}
    settlement = analysis.get("settlement") or {}
    defense_pkg = analysis.get("defense_package") or {}
    legal = analysis.get("legal") or {}
    dna = analysis.get("activist_dna_top") or {}
    pa = analysis.get("proxy_advisor") or {}
    cg = analysis.get("claim_graph") or {}
    mr = analysis.get("market_reaction") or {}

    p1 = sim.get("p_activist_wins_1_plus", 0) or 0
    p2 = sim.get("p_activist_wins_2_plus", 0) or 0

    # damaging claim - either field name works
    strongest = cg.get("strongest_claims") or []
    if strongest:
        damaging = strongest[0].get("claim_text") or strongest[0].get("claim") or "—"
    else:
        damaging = "No high-power claim identified."

    return [
        {
            "q": "How vulnerable are we, really?",
            "a": (f"Final risk level: {final.get('final_risk_level', '—')}. "
                  f"12-month probability of an activism event: "
                  f"{_pct(final.get('activism_event_probability_12m'))}. "
                  f"If attacked, P(losing ≥1 board seat): {_pct(p1)}; "
                  f"P(losing ≥2): {_pct(p2)}."),
        },
        {
            "q": "Who is most likely to come after us?",
            "a": (f"Most likely profile: {dna.get('name', '—')} "
                  f"— style: {dna.get('likely_campaign_style', '—')}; "
                  f"likely stake ~{dna.get('likely_stake_pct', '–')}%; "
                  f"likely seats requested: {dna.get('likely_board_seats_requested', '–')}. "
                  f"Why: {dna.get('why_this_activist_type', '—')}"),
        },
        {
            "q": "What is the most damaging claim they will make?",
            "a": damaging,
        },
        {
            "q": "If a campaign goes public, what's the most likely outcome?",
            "a": (f"Most likely outcome bucket: P(private settlement) "
                  f"{_pct(sim.get('p_private_settlement'))}; "
                  f"P(public proxy contest) {_pct(sim.get('p_proxy_vote'))}; "
                  f"P(strategic review forced) {_pct(sim.get('p_strategic_review'))}. "
                  f"Expected seats won by activist: {sim.get('expected_seats_won', '–')}."),
        },
        {
            "q": "Do we have the shareholder votes to win a contested vote today?",
            "a": (f"Modeled coalition: activist {coalition.get('expected_activist_vote_pct', '–')}% / "
                  f"management {coalition.get('expected_management_vote_pct', '–')}% / "
                  f"abstain {coalition.get('expected_abstain_pct', '–')}%. "
                  f"Below 50% activist coalition is the threshold for a full defense."),
        },
        {
            "q": "Should we settle or fight?",
            "a": (f"Recommended path: {settlement.get('recommended_path', '—')}. "
                  f"Best option modeled: {settlement.get('best_option', {}).get('option_name', '—')} "
                  f"(utility {settlement.get('best_option', {}).get('utility_score', '–')}/100). "
                  f"Runner-up: {settlement.get('runner_up_option', {}).get('option_name', '—')}."),
        },
        {
            "q": "What are the top three things we should do in the next 30 days?",
            "a": _top_actions(defense_pkg, n=3),
        },
        {
            "q": "How much time do we have on the calendar?",
            "a": (f"Annual meeting in {legal.get('days_to_annual_meeting', '–')} days; "
                  f"nomination deadline in {legal.get('days_to_nomination_deadline', '–')} days "
                  f"(missed: {legal.get('deadline_missed', '—')}). "
                  f"Legal feasibility for activist: {legal.get('legal_feasibility_score', '–')}/100."),
        },
        {
            "q": "What's the proxy advisor going to say?",
            "a": (f"P(ISS-style support for our full slate): "
                  f"{_pct(pa.get('p_support_management_full_slate'))}; "
                  f"P(support 1 activist nominee): "
                  f"{_pct(pa.get('p_support_one_activist_nominee'))}; "
                  f"P(support 2+ activist nominees): "
                  f"{_pct(pa.get('p_support_two_plus_activist_nominees'))}; "
                  f"PA governance concern score: "
                  f"{pa.get('pa_governance_concern_score', '–')}/100."),
        },
        {
            "q": "What is the dollar value at stake if we lose control?",
            "a": (f"Risk-to-stock-story: {mr.get('risk_to_stock_story', '—')}. "
                  f"Expected probability-weighted market reaction: "
                  f"{mr.get('expected_reaction_weighted_pp', '–')} pp."),
        },
    ]


def generate_investor_talking_points(analysis):
    """Short, plain-language script for IR to use on holder calls."""
    primary = analysis.get("primary_thesis") or {}
    defense = analysis.get("defense") or {}
    defense_pkg = analysis.get("defense_package") or {}
    coalition = analysis.get("coalition") or {}

    points = [
        f"We have heard the concerns regarding {primary.get('name', 'value realization')}. "
        f"We disagree with the framing, and here's why."
    ]
    for w in (defense.get("strongest_defenses") or [])[:2]:
        if isinstance(w, dict):
            label = w.get("label", w.get("name", ""))
            expl = w.get("explanation", "")
        else:
            label, expl = str(w), ""
        points.append(f"Our strongest record: {label}. {expl}".strip())

    rec = (defense_pkg.get("recommended_actions") or [])[:3]
    if rec:
        points.append("We are not standing still — we are already moving on: "
                      + "; ".join(a.get("action_name", "") for a in rec) + ".")
    if coalition.get("expected_management_vote_pct"):
        points.append(
            f"Our shareholder base is engaged: ~{coalition.get('expected_management_vote_pct')}% "
            f"of modeled holders are inclined to support the current Board."
        )
    points.append("We welcome substantive engagement and will continue to update the "
                  "market on progress.")
    return points


def generate_press_narrative(analysis):
    """Holding statement template if/when an activist surfaces publicly."""
    company = analysis.get("company") or {}
    name = company.get("name", "the Company")
    primary = analysis.get("primary_thesis") or {}
    defense_pkg = analysis.get("defense_package") or {}

    # work around backslash-in-fstring weirdness
    topic = primary.get("name") or "the company's strategic direction"

    lines = [
        f"# {name} — Holding Statement (DRAFT)",
        "",
        f"{name} has received correspondence from a shareholder regarding {topic}. "
        "The Board welcomes input from all shareholders and regularly reviews "
        "opportunities to enhance long-term shareholder value.",
        "",
        "The Board and management team remain focused on execution of the Company's "
        "strategy. We have a clear plan in place, including:",
    ]
    for a in (defense_pkg.get("recommended_actions") or [])[:3]:
        lines.append(f"- {a.get('action_name', '—')}")
    lines += [
        "",
        "The Company will not comment further on private shareholder communications at this time.",
        "",
        "---",
        f"*{COMPLIANCE_NOTE}*",
    ]
    return "\n".join(lines)


def generate_war_room_outputs(analysis):
    return {
        "red_team_attack": generate_red_team_attack(analysis),
        "blue_team_defense": generate_blue_team_defense(analysis),
        "board_qa": generate_board_qa(analysis),
        "investor_talking_points": generate_investor_talking_points(analysis),
        "press_narrative": generate_press_narrative(analysis),
    }
