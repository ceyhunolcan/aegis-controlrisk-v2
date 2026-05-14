# Single (company, historical campaign, model output) -> markdown case study.
# Used in the backtesting docs to show side-by-side what the model predicted
# vs what actually happened.

_JUNK = {"and", "or", "the", "a", "an", "of", "in", "to", "for", "with", "&"}


def _pct(x, default="–"):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return f"{v * 100:.0f}%" if v <= 1.0 else f"{v:.0f}%"


def _loose_match(a, b):
    if not a or not b:
        return False
    sa = set(a.lower().replace("/", " ").split()) - _JUNK
    sb = set(b.lower().replace("/", " ").split()) - _JUNK
    return bool(sa & sb)


def generate_case_study(company, campaign, model_outputs):
    company = company or {}
    campaign = campaign or {}
    model_outputs = model_outputs or {}

    name = company.get("name", "Company")
    ticker = company.get("ticker", "—")

    activist      = campaign.get("activist_name", "Activist")
    actual_thesis = campaign.get("thesis_type", "—")
    seats_won     = campaign.get("board_seats_won", 0)
    settled       = campaign.get("settled", False)
    went_to_vote  = campaign.get("went_to_vote", False)
    outcome       = campaign.get("outcome", "—")
    stock_30d     = campaign.get("stock_reaction_30d", "—")

    vuln       = model_outputs.get("vulnerability") or {}
    final      = model_outputs.get("final_score") or {}
    primary    = model_outputs.get("primary_thesis") or {}
    sim        = model_outputs.get("simulation") or {}
    settlement = model_outputs.get("settlement") or {}

    # call quality (loose)
    thesis_call = _loose_match(primary.get("name", ""), actual_thesis or "")
    seat_call = (int(seats_won or 0) >= 1) == (
        (sim.get("p_activist_wins_1_plus", 0) or 0) >= 0.5
    )
    settle_call = bool(settled) == bool(
        settlement.get("recommended_path", "").lower().startswith("settle")
    )

    return "\n".join([
        f"# Case Study: {name} ({ticker}) vs {activist}",
        "",
        f"**Historical campaign outcome:** {outcome}",
        "",
        "## The actual campaign",
        "",
        f"- Activist: **{activist}**",
        f"- Actual thesis: {actual_thesis}",
        f"- Settled: {settled}",
        f"- Went to vote: {went_to_vote}",
        f"- Board seats won by activist: {seats_won}",
        f"- Stock reaction (30d): {stock_30d}",
        "",
        "## What the CASCADE-2 model said",
        "",
        f"- Vulnerability: **{vuln.get('score', '–')}/100** ({vuln.get('level', '—')})",
        f"- 12-month activism event probability: "
        f"**{_pct(final.get('activism_event_probability_12m'))}**",
        f"- Most-likely thesis predicted: **{primary.get('name', '—')}**",
        f"- P(activist wins ≥1 seat) in proxy contest: "
        f"**{_pct(sim.get('p_activist_wins_1_plus'))}**",
        f"- Recommended path: **{settlement.get('recommended_path', '—')}** "
        f"(best option: {settlement.get('best_option', {}).get('option_name', '—')})",
        "",
        "## Did the model call it?",
        "",
        f"- Thesis match: **{'yes' if thesis_call else 'partial / no'}**",
        f"- Seat-loss direction called correctly: **{'yes' if seat_call else 'no'}**",
        f"- Settlement direction called correctly: **{'yes' if settle_call else 'no'}**",
        "",
    ])
