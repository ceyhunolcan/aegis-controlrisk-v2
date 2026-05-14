# Memo writers. The dashboard download buttons pull from these.
#
# Important rule: every accessor uses .get() with a default. The pipeline tries
# very hard to populate every key but if any one of the upstream engines blew
# up and got swallowed, we'd rather print "—" than crash here. The memo is the
# part bankers actually screenshot.
from datetime import date

from config import COMPLIANCE_NOTE, APP_TITLE


# tiny formatting helpers ------------------------------------------------

def _safe(d, *path, default=""):
    cur = d
    for k in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k, default)
        else:
            cur = getattr(cur, k, default)
    return cur if cur is not None else default


def _pct(x, default="–"):
    """0..1 -> '40%', 0..100 -> '40.0%'. yes it's hacky."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return f"{v * 100:.0f}%" if v <= 1.0 else f"{v:.1f}%"


def _score(x, default="–"):
    try:
        return f"{float(x):.0f}"
    except (TypeError, ValueError):
        return default


def _bullets(items, max_items=5, default="(none identified)"):
    """Render list or dict of items as markdown bullets."""
    if not items:
        return default
    if isinstance(items, dict):
        out = []
        for k, v in list(items.items())[:max_items]:
            if isinstance(v, bool):
                if v:
                    out.append(f"- {k}: yes")
            elif v in (None, "", 0):
                continue
            else:
                out.append(f"- {k}: {v}")
        return "\n".join(out) if out else default
    try:
        sliced = list(items)[:max_items]
    except Exception:
        return str(items)
    out = []
    for it in sliced:
        if isinstance(it, dict):
            label = (it.get("name") or it.get("title") or it.get("label")
                     or it.get("claim") or it.get("explanation") or str(it))
            out.append(f"- {label}")
        else:
            out.append(f"- {it}")
    return "\n".join(out) if out else default


# board memo -------------------------------------------------------------

def generate_board_memo(analysis):
    """The 15-section board briefing. Returns markdown."""
    if not isinstance(analysis, dict):
        return "[Memo generation error: invalid analysis input]"

    company   = analysis.get("company") or {}
    vuln      = analysis.get("vulnerability") or {}
    fix       = analysis.get("fixability") or {}
    final     = analysis.get("final_score") or {}
    legal     = analysis.get("legal") or {}
    triggers  = analysis.get("triggers") or {}
    primary   = analysis.get("primary_thesis") or {}
    coalition = analysis.get("coalition") or {}
    pa        = analysis.get("proxy_advisor") or {}
    defense   = analysis.get("defense") or {}
    sim       = analysis.get("simulation") or {}
    settlement= analysis.get("settlement") or {}
    bank_opp  = analysis.get("bank_opportunity") or {}
    director_scores = analysis.get("director_scores") or []
    swing     = analysis.get("swing_shareholders") or {}
    dna_top   = analysis.get("activist_dna_top") or {}
    defense_pkg = analysis.get("defense_package") or {}
    market    = analysis.get("market_reaction") or {}
    claim_graph = analysis.get("claim_graph") or {}

    name   = company.get("name", "the Company")
    ticker = company.get("ticker", "—")
    sector = company.get("sector", "—")

    P = []
    add = P.append

    add(f"# {APP_TITLE}: Board Briefing Memo")
    add(f"**Company:** {name} ({ticker})  ")
    add(f"**Sector:** {sector}  ")
    add(f"**Memo date:** {date.today().isoformat()}  ")
    add("**Classification:** Privileged & Confidential — Board Use Only")
    add("")
    add("---")
    add("")

    # 1. Exec summary
    add("## 1. Executive Summary")
    add("")
    add(_safe(final, "executive_summary", default="No executive summary available."))
    add("")
    add(
        f"- **Final Risk Level:** {final.get('final_risk_level', '—')}  \n"
        f"- **Activism Event Probability (12m):** {_pct(final.get('activism_event_probability_12m'))}  \n"
        f"- **Control-Loss Probability if Attacked:** {_pct(final.get('control_loss_probability_if_attacked'))}  \n"
        f"- **Board-Seat Loss Probability:** {_pct(final.get('board_seat_loss_probability'))}  \n"
        f"- **Settlement Pressure Index:** {_score(final.get('settlement_pressure_index'))} / 100"
    )
    add("")

    # 2. Vuln & Fix
    add("## 2. Vulnerability & Fixability Assessment")
    add("")
    add(f"**Vulnerability:** {_score(vuln.get('score'))} / 100 — {vuln.get('level', '—')}  ")
    add(f"**Fixability:** {_score(fix.get('score'))} / 100 — {fix.get('classification', '—')}  ")
    add("")
    add("**Top vulnerability drivers:**")
    add(_bullets(vuln.get("explanation") or [], max_items=5))
    add("")

    # 3. Primary thesis
    add("## 3. Most-Likely Activist Thesis")
    add("")
    add(f"**Thesis:** {primary.get('name', '—')} — power score {_score(primary.get('score'))}/100")
    add("")
    add(f"**Recommended ask:** {primary.get('recommended_ask', '—')}")
    add("")
    add(f"**Estimated upside range:** {primary.get('estimated_upside_range', '—')}")
    add("")
    add("**Likely activist memo angle:**")
    add("> " + str(primary.get("activist_attack_memo", "No memo content."))
        .replace("\n", "\n> "))
    add("")
    add("**Top supporting evidence (activist view):**")
    add(_bullets(primary.get("evidence_bullets") or [], max_items=5))
    add("")
    add("**Risks to thesis (defense angles):**")
    add(_bullets(primary.get("risks_to_thesis") or [], max_items=5))
    add("")

    # 4. Activist DNA
    add("## 4. Likely Activist Profile")
    add("")
    if dna_top:
        add(f"**Most likely activist archetype:** {dna_top.get('name', '—')} "
            f"(fit score {_score(dna_top.get('fit_score'))}/100)")
        add("")
        add(f"- Likely campaign style: {dna_top.get('likely_campaign_style', '—')}")
        add(f"- Likely stake range: ~{dna_top.get('likely_stake_pct', '—')}%")
        add(f"- Likely board seats requested: {dna_top.get('likely_board_seats_requested', '—')}")
        add("")
        add(f"**Why this archetype:** {dna_top.get('why_this_activist_type', '—')}")
    else:
        add("(No archetype match identified.)")
    add("")

    # 5. Board vulnerability map
    add("## 5. Board Vulnerability Map")
    add("")
    if director_scores:
        ranked = sorted(director_scores, key=lambda d: -float(d.get("score", 0) or 0))
        add("Directors ranked by replaceability risk (highest first):")
        add("")
        add("| Director | Score | Risk | Tenure | Independent | Committee Chair |")
        add("|---|---|---|---|---|---|")
        for d in ranked[:7]:
            add(
                f"| {d.get('name', '—')} "
                f"| {_score(d.get('score'))} "
                f"| {d.get('risk_level', '—')} "
                f"| {d.get('tenure_years', '—')}y "
                f"| {'Y' if d.get('independent') else 'N'} "
                f"| {'Y' if d.get('is_committee_chair') else 'N'} |"
            )
    else:
        add("(Director scoring not available.)")
    add("")

    # 6. Strongest claims
    add("## 6. Most Powerful Claims Against Management")
    add("")
    strongest = claim_graph.get("strongest_claims") or []
    if strongest:
        add("Top activist claims by power score:")
        for c in strongest[:5]:
            add(
                f"- **{c.get('claim_text', c.get('claim', '—'))}** "
                f"— power {_score(c.get('claim_power_score'))}/100 "
                f"(rebuttability {_score(c.get('rebuttability'))})"
            )
    else:
        add("(No claim graph data.)")
    add("")

    # 7. Coalition
    add("## 7. Shareholder Coalition Math")
    add("")
    add(
        f"- Expected activist coalition vote: {_score(coalition.get('expected_activist_vote_pct'))}%  \n"
        f"- Expected management vote: {_score(coalition.get('expected_management_vote_pct'))}%  \n"
        f"- Expected abstain: {_score(coalition.get('expected_abstain_pct'))}%"
    )
    add("")
    by_type = coalition.get("by_holder_type") or {}
    if by_type:
        add("**Breakdown by holder type (likely activist support %):**")
        for ht, v in list(by_type.items())[:8]:
            if isinstance(v, dict):
                add(f"- {ht}: {_score(v.get('activist_support_pct'))}% activist support")
            else:
                add(f"- {ht}: {v}")
    add("")

    # 8. Swing shareholders
    add("## 8. Priority Outreach: Swing Shareholders")
    add("")
    top_swing = swing.get("top_5_priority_outreach") or []
    if top_swing:
        add("Top-5 shareholders to engage proactively:")
        for s in top_swing[:5]:
            add(
                f"- **{s.get('holder_name', '—')}** "
                f"(swing score {_score(s.get('swing_value_score'))}, "
                f"ownership {_score(s.get('ownership_pct'))}%): "
                f"{s.get('outreach_recommendation', '')}"
            )
    else:
        add("(No swing shareholders identified.)")
    add("")

    # 9. Proxy advisor
    add("## 9. Proxy Advisor Shadow Report (ISS/Glass Lewis posture)")
    add("")
    add(
        f"- P(PA supports full management slate): {_pct(pa.get('p_support_management_full_slate'))}  \n"
        f"- P(PA supports one activist nominee): {_pct(pa.get('p_support_one_activist_nominee'))}  \n"
        f"- P(PA supports two+ activist nominees): {_pct(pa.get('p_support_two_plus_activist_nominees'))}  \n"
        f"- P(PA recommends against say-on-pay): {_pct(pa.get('p_recommend_against_pay'))}  \n"
        f"- PA governance concern score: {_score(pa.get('pa_governance_concern_score'))}/100"
    )
    add("")
    if pa.get("recommended_preemptive_steps"):
        add("**Recommended pre-emptive steps to win PA support:**")
        add(_bullets(pa.get("recommended_preemptive_steps"), max_items=5))
    add("")

    # 10. Monte Carlo
    add("## 10. Proxy Contest Monte Carlo Simulation")
    add("")
    add(f"Across {sim.get('n_simulations', '–')} simulations (seed {sim.get('random_seed', '–')}):\n")
    add(
        f"- P(private settlement before vote): {_pct(sim.get('p_private_settlement'))}  \n"
        f"- P(public proxy contest): {_pct(sim.get('p_proxy_vote'))}  \n"
        f"- P(activist wins ≥1 seat): **{_pct(sim.get('p_activist_wins_1_plus'))}**  \n"
        f"- P(activist wins ≥2 seats): {_pct(sim.get('p_activist_wins_2_plus'))}  \n"
        f"- P(activist wins ≥3 seats): {_pct(sim.get('p_activist_wins_3_plus'))}  \n"
        f"- P(company fully defends): {_pct(sim.get('p_company_full_defense'))}  \n"
        f"- P(strategic review forced): {_pct(sim.get('p_strategic_review'))}  \n"
        f"- Expected seats won by activist: {sim.get('expected_seats_won', '–')}"
    )
    add("")
    add(f"**Interpretation:** {sim.get('interpretation', '')}")
    add("")

    # 11. Defense readiness
    add("## 11. Current Defense Readiness")
    add("")
    add(f"**Defense strength:** {_score(defense.get('defense_strength_score'))}/100 "
        f"— {defense.get('defense_level', '—')}")
    add("")
    add("**Strongest defenses:**")
    add(_bullets(defense.get("strongest_defenses") or [], max_items=4))
    add("")
    add("**Weakest defenses:**")
    add(_bullets(defense.get("weakest_defenses") or [], max_items=4))
    add("")
    add(f"**Recommended response strategy:** {defense.get('recommended_response_strategy', '—')}")
    add("")

    # 12. Defense package
    add("## 12. Recommended Defense Package (90-Day Plan)")
    add("")
    add(
        f"Estimated risk reduction: **{_score(defense_pkg.get('estimated_risk_before'))} → "
        f"{_score(defense_pkg.get('estimated_risk_after'))}** "
        f"(–{_score(defense_pkg.get('estimated_risk_reduction'))} pts)"
    )
    add("")
    if defense_pkg.get("recommended_actions"):
        add("**Top recommended actions:**")
        for a in defense_pkg.get("recommended_actions")[:5]:
            add(f"- **{a.get('action_id', '')}: {a.get('action_name', '—')}** "
                f"— efficiency {_score(a.get('efficiency_score'))}")
    add("")
    plan = defense_pkg.get("ninety_day_plan") or []
    if plan:
        add("**90-Day execution timeline:**")
        if isinstance(plan, dict):
            for bucket, items in plan.items():
                add(f"- *{bucket}:* {', '.join(items) if isinstance(items, list) else items}")
        else:
            for step in plan:
                if isinstance(step, dict):
                    add(f"- *{step.get('timing', '—')}*: {step.get('action', '—')} "
                        f"(category: {step.get('category', '—')}, "
                        f"expected risk reduction: {step.get('expected_reduction', '–')})")
                else:
                    add(f"- {step}")
    add("")

    # 13. Settlement vs fight
    add("## 13. Settlement-vs-Fight Game Theory")
    add("")
    add(f"**Recommended path:** {settlement.get('recommended_path', '—')}")
    add("")
    best = settlement.get("best_option") or {}
    if best:
        add(f"**Best option:** {best.get('option_name', '—')} "
            f"— utility {_score(best.get('utility_score'))}/100")
        add(f"  - Risk reduction: {_score(best.get('risk_reduction'))}")
        add(f"  - Shareholder acceptance: {_score(best.get('shareholder_acceptance'))}")
    runner = settlement.get("runner_up_option") or {}
    if runner:
        add(f"**Runner-up:** {runner.get('option_name', '—')} "
            f"— utility {_score(runner.get('utility_score'))}/100")
    add("")
    add("**Suggested negotiation script:**")
    add("> " + str(settlement.get("negotiation_script", "")).replace("\n", "\n> "))
    add("")

    # 14. Legal calendar
    add("## 14. Legal Calendar & Structural Defenses")
    add("")
    add(
        f"- Annual meeting date: {legal.get('annual_meeting_date', '—')}  \n"
        f"- Nomination deadline: {legal.get('nomination_deadline', '—')}  \n"
        f"- Days to annual meeting: {legal.get('days_to_annual_meeting', '—')}  \n"
        f"- Days to nomination deadline: {legal.get('days_to_nomination_deadline', '—')}  \n"
        f"- Nomination deadline missed: {legal.get('deadline_missed', '—')}  \n"
        f"- Legal feasibility for activist: {_score(legal.get('legal_feasibility_score'))}/100  \n"
        f"- Urgency: {_score(legal.get('urgency_score'))}/100"
    )
    add("")
    if legal.get("structural_flags"):
        add("**Structural defense flags:**")
        add(_bullets(legal.get("structural_flags"), max_items=8))
    add("")
    if legal.get("warnings"):
        add("**Calendar warnings:**")
        add(_bullets(legal.get("warnings"), max_items=5))
    add("")

    # 15. Triggers
    add("## 15. Active Triggers & Monitoring")
    add("")
    add(f"**Trigger score:** {_score(triggers.get('trigger_score'))}/100 "
        f"— urgency {triggers.get('urgency_level', '—')}")
    add("")
    if triggers.get("active_triggers"):
        add("**Active triggers:**")
        for t in triggers.get("active_triggers")[:6]:
            if isinstance(t, dict):
                add(f"- {t.get('trigger_type', '—')}: {t.get('description', '')}")
            else:
                add(f"- {t}")
    add("")
    if triggers.get("recommended_monitoring_actions"):
        add("**Recommended monitoring actions:**")
        add(_bullets(triggers.get("recommended_monitoring_actions"), max_items=5))
    add("")

    # Appendix A
    add("## Appendix A: Advisory Opportunity Summary")
    add("")
    add(f"- Mandate opportunity score: {_score(bank_opp.get('mandate_opportunity_score'))}/100 "
        f"— {bank_opp.get('opportunity_level', '—')}")
    for p in (bank_opp.get("likely_advisory_products") or [])[:5]:
        if isinstance(p, dict):
            add(f"  - {p.get('product', p.get('name', '—'))}")
        else:
            add(f"  - {p}")
    add("")

    # Appendix B
    add("## Appendix B: Expected Market Reaction")
    add("")
    add(f"- Expected probability-weighted stock reaction: {market.get('expected_reaction_weighted_pp', '–')} pp")
    add(f"- Risk to stock narrative: {market.get('risk_to_stock_story', '—')}")
    add("")

    add("---")
    add("")
    add(f"*{COMPLIANCE_NOTE} Synthetic data; for demonstration purposes only.*")

    return "\n".join(P)


# Attack memo (red team) -------------------------------------------------

def generate_attack_memo(analysis):
    company = analysis.get("company") or {}
    name = company.get("name", "the Company")
    ticker = company.get("ticker", "—")

    primary = analysis.get("primary_thesis") or {}
    dna_top = analysis.get("activist_dna_top") or {}
    slate = analysis.get("slate") or {}
    claim_graph = analysis.get("claim_graph") or {}

    out = [
        f"# Open Letter to the Board of {name} ({ticker})",
        "",
        f"*From: {dna_top.get('name', 'Concerned Shareholder')}*",
        "",
        "---",
        "",
        "## Why we are writing",
        "",
        primary.get("activist_attack_memo")
            or f"We have accumulated a meaningful position in {name} and believe value is materially under-realized.",
        "",
        "## Our core thesis",
        "",
        f"**{primary.get('name', 'Value-realization thesis')}** — {primary.get('recommended_ask', '')}.",
        "",
        f"We believe a credible path exists to **{primary.get('estimated_upside_range', 'meaningful upside')}**.",
        "",
        "## The evidence",
        "",
    ]
    for e in (primary.get("evidence_bullets") or [])[:6]:
        out.append(f"- {e}")
    strongest = claim_graph.get("strongest_claims") or []
    if strongest:
        out.append("")
        out.append("Further, the record shows:")
        for c in strongest[:4]:
            out.append(f"- {c.get('claim_text', c.get('claim', ''))}")
    out += [
        "",
        "## What we are asking the Board to do",
        "",
        f"- {primary.get('recommended_ask', 'Begin a strategic review.')}",
    ]
    nominees = slate.get("recommended_slate") or slate.get("slate") or []
    if nominees:
        out.append("- Add the following independent nominees to the Board:")
        for n in nominees[:3]:
            out.append(f"  - **{n.get('nominee_name', n.get('name', '—'))}** "
                       f"— {n.get('profile_type', n.get('profile', ''))}")
    out += [
        "",
        "## What happens next",
        "",
        "We would prefer constructive engagement. We are, however, prepared to take this case "
        "directly to shareholders should the Board decline good-faith dialogue.",
        "",
        "---",
        f"*{COMPLIANCE_NOTE}*",
    ]
    return "\n".join(out)


# Defense memo (blue team) -----------------------------------------------

def generate_defense_memo(analysis):
    company = analysis.get("company") or {}
    name = company.get("name", "the Company")
    defense = analysis.get("defense") or {}
    claim_defense_table = analysis.get("claim_defense_table") or []
    defense_pkg = analysis.get("defense_package") or {}

    out = [
        f"# {name} — Management Response Memo",
        "",
        "**To:** Activist counterparties and proxy advisors",
        "**From:** Office of the CEO and Lead Independent Director",
        "",
        "---",
        "",
        "## Our position",
        "",
        defense.get("management_rebuttal_memo",
                    "We are confident in the Company's strategic direction and the Board's composition."),
        "",
        "## Point-by-point rebuttals",
        "",
    ]
    for row in claim_defense_table[:6]:
        out.append(f"**Claim:** {row.get('claim', '—')}")
        out.append("")
        out.append(f"**Our response:** {row.get('management_defense', row.get('defense_response', '—'))}")
        out.append("")
    out += ["## Proactive actions we are taking", ""]
    for a in (defense_pkg.get("recommended_actions") or [])[:5]:
        out.append(f"- **{a.get('action_name', '—')}** — "
                   f"{a.get('rationale', a.get('description', ''))}")
    out += ["", "---", f"*{COMPLIANCE_NOTE}*"]
    return "\n".join(out)


# Banker pitch -----------------------------------------------------------

def generate_banker_pitch_memo(analysis):
    company = analysis.get("company") or {}
    name = company.get("name", "the Company")
    ticker = company.get("ticker", "—")
    bank = analysis.get("bank_opportunity") or {}
    final = analysis.get("final_score") or {}

    out = [
        f"# Advisory Opportunity: {name} ({ticker})",
        "",
        f"**Mandate score:** {_score(bank.get('mandate_opportunity_score'))}/100 "
        f"— {bank.get('opportunity_level', '—')}",
        "",
        "## Why this client now",
        "",
        bank.get("banker_pitch_angle", "—"),
        "",
        f"**Current activism risk:** {final.get('final_risk_level', '—')}, "
        f"with P(activism event 12m) = {_pct(final.get('activism_event_probability_12m'))}.",
        "",
        "## Suggested products",
        "",
    ]
    for p in (bank.get("likely_advisory_products") or [])[:6]:
        if isinstance(p, dict):
            out.append(f"- **{p.get('product', p.get('name', '—'))}**: "
                       f"{p.get('rationale', p.get('description', ''))}")
        else:
            out.append(f"- {p}")
    out += [
        "",
        "## Suggested client email",
        "",
        "> " + str(bank.get("suggested_client_email", "")).replace("\n", "\n> "),
        "",
        "## Board-meeting pitch summary",
        "",
        bank.get("board_meeting_pitch_summary", "—"),
        "",
        "---",
        f"*{COMPLIANCE_NOTE}*",
    ]
    return "\n".join(out)
