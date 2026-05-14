# Streamlit dashboard. Run with `streamlit run app.py`.
#
# This is intentionally just a presentation layer over the analysis dict
# returned by run_company_analysis(). No business logic here - if you find
# yourself adding a calc, push it into aegis/scoring/ or aegis/simulation/
# and re-read it back from the dict.
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis
from config import APP_TITLE, APP_TAGLINE, COMPLIANCE_NOTE


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Light styling - mostly to avoid the default Streamlit gray background
# making everything look like a tax-prep app.
st.markdown(
    """
    <style>
      .stApp { background-color: #fafafa; }
      h1, h2, h3 { color: #0a2540; }
      .risk-critical { color: #b00020; font-weight: 700; }
      .risk-high { color: #d96b00; font-weight: 700; }
      .risk-moderate { color: #c8a200; font-weight: 700; }
      .risk-low { color: #2e7d32; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _load_data():
    return load_all_data("data")


@st.cache_data(show_spinner="Running CASCADE-2 analysis pipeline...")
def _analyze(company_id):
    return run_company_analysis(company_id, _load_data())


# helpers ----------------------------------------------------------------

def pct(v, default="—"):
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f"{f * 100:.0f}%" if f <= 1.0 else f"{f:.0f}%"


_RISK_CSS = {"Critical": "risk-critical", "High": "risk-high",
             "Moderate": "risk-moderate", "Low": "risk-low"}


def gauge(score, title, max_val=100):
    score = float(score or 0)
    # green / yellow / orange / red bands match RISK_LEVELS thresholds
    color = "#2e7d32"
    if score >= 80:
        color = "#b00020"
    elif score >= 65:
        color = "#d96b00"
    elif score >= 45:
        color = "#c8a200"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, max_val]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 45], "color": "#e8f5e9"},
                {"range": [45, 65], "color": "#fff8e1"},
                {"range": [65, 80], "color": "#fbe9e7"},
                {"range": [80, 100], "color": "#ffcdd2"},
            ],
        },
    ))
    fig.update_layout(height=200, margin=dict(t=40, b=10, l=10, r=10))
    return fig


def component_bar(components, title):
    if not components:
        return go.Figure()
    items = sorted(components.items(), key=lambda kv: -float(kv[1] or 0))
    fig = go.Figure(go.Bar(
        x=[float(v or 0) for _, v in items],
        y=[k.replace("_", " ").title() for k, _ in items],
        orientation="h",
        marker_color="#0a2540",
    ))
    fig.update_layout(
        title=title, height=350,
        margin=dict(t=40, b=20, l=10, r=10),
        xaxis_range=[0, 100],
    )
    return fig


# sidebar + company selection --------------------------------------------

st.sidebar.title("🛡️ " + APP_TITLE)
st.sidebar.caption(APP_TAGLINE)
st.sidebar.markdown("---")

data = _load_data()
companies_df = data["companies"]
options = [(row["company_id"], f"{row['ticker']} — {row['name']}")
           for _, row in companies_df.iterrows()]

choice = st.sidebar.selectbox(
    "Company",
    options=[c[0] for c in options],
    format_func=lambda cid: dict(options)[cid],
)

# the one expensive call (moved up so the snapshot tools can use it)
analysis = _analyze(choice)
company = analysis.get("company") or {}
final = analysis.get("final_score") or {}
risk_level = final.get("final_risk_level", "—")


# Snapshot + alerts tooling. Saving a snapshot writes a timestamped JSON to
# `snapshots/`; the next time the user runs the same company, the app can
# diff against the most recent snapshot and surface alerts.
st.sidebar.markdown("---")
st.sidebar.subheader("Audit + alerts")

from aegis.audit.snapshots import save_snapshot, list_snapshots, load_snapshot
from aegis.alerts.rules import check_alerts

existing_snaps = list_snapshots(company_id=choice)
if existing_snaps:
    st.sidebar.caption(f"{len(existing_snaps)} snapshot(s) on disk.")
    # Diff against the most recent one
    most_recent = existing_snaps[-1]
    try:
        prior = load_snapshot(most_recent["path"]).get("analysis")
        alerts = check_alerts(prior, analysis)
    except Exception:
        alerts = []
    if alerts:
        st.sidebar.warning(f"{len(alerts)} alert(s) since last snapshot")
        for a in alerts[:3]:
            st.sidebar.caption(f"• [{a['severity']}] {a['rule_name']}")
    else:
        st.sidebar.caption("No alerts since last snapshot.")
else:
    st.sidebar.caption("No snapshots yet for this company.")

note = st.sidebar.text_input("Snapshot note (optional)", "")
if st.sidebar.button("📸 Save snapshot"):
    rec = save_snapshot(analysis, note=note)
    st.sidebar.success(f"Saved: {rec['snapshot_id']}")


st.sidebar.markdown("---")
st.sidebar.caption(f"*{COMPLIANCE_NOTE}*")
st.sidebar.caption("Synthetic data — for demonstration only.")


# header -----------------------------------------------------------------
st.title(f"{company.get('name', 'Company')} ({company.get('ticker', '—')})")
st.markdown(
    f"**Sector:** {company.get('sector', '—')} &nbsp;|&nbsp; "
    f"**Risk:** <span class='{_RISK_CSS.get(risk_level, '')}'>"
    f"{risk_level}</span> &nbsp;|&nbsp; "
    f"**P(activism 12m):** {pct(final.get('activism_event_probability_12m'))} "
    f"&nbsp;|&nbsp; "
    f"**Score:** {float(final.get('activism_risk_score_0_100', 0)):.0f}/100",
    unsafe_allow_html=True,
)
st.markdown("---")


# Three-layer information architecture.
# Default lands the user on the executive view (Layer 1). Layer 2 is the
# question-based deep dives ("Who / What / When"). Layer 3 is the original
# 16-engine tab layout for analysts.
view_mode = st.sidebar.radio(
    "View mode",
    ["Executive (60-sec)", "Question deep-dive (15-min)", "Analyst detail (full)"],
    index=0,
)

from aegis.reports.executive_view import (
    executive_verdict, top_three_reasons, recommended_next_action,
)
from aegis.reports.question_views import all_layer2_views


if view_mode == "Executive (60-sec)":
    st.subheader("Verdict")
    st.markdown(executive_verdict(analysis))
    st.markdown("")
    st.subheader("Top three reasons")
    for i, reason in enumerate(top_three_reasons(analysis), start=1):
        st.markdown(f"{i}. {reason}")
    st.markdown("")
    st.subheader("What to do this week")
    st.markdown(recommended_next_action(analysis))

    st.markdown("---")
    st.caption("Switch to **Question deep-dive** in the sidebar for the 15-minute "
               "view, or **Analyst detail** for the full 16-tab engine output.")
    st.stop()  # Layer 1 only - don't render the rest


if view_mode == "Question deep-dive (15-min)":
    views = all_layer2_views(analysis)
    who_t, what_t, when_t = st.tabs(["Who", "What", "When"])

    with who_t:
        v = views["who"]
        st.subheader(v["subtitle"])

        a = v["attacker"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Archetype", a.get("archetype", "—"))
        c2.metric("Fit", f"{a.get('fit_score', 0):.0f}/100"
                  if a.get("fit_score") is not None else "—")
        c3.metric("Likely stake", f"~{a.get('likely_stake_pct', '–')}%")
        st.markdown(f"**Style:** {a.get('style', '—')}")
        st.markdown(f"**Why this archetype:** {a.get('rationale', '—')}")

        st.markdown("### Most exposed directors")
        for d in v["high_risk_directors"]:
            with st.expander(f"{d.get('name', '—')} — "
                             f"{d.get('score', '–')}/100 "
                             f"({d.get('risk_level', '—')})"):
                st.markdown(f"**Best attack angle:** "
                            f"{d.get('best_attack_angle', '—')}")
                st.markdown(f"**Replacement profile:** "
                            f"{d.get('replacement_profile', '—')}")

        cs = v["coalition_summary"]
        st.markdown("### Coalition math")
        c1, c2, c3 = st.columns(3)
        c1.metric("Activist", f"{cs.get('activist_pct', '–')}%")
        c2.metric("Management", f"{cs.get('management_pct', '–')}%")
        c3.metric("Abstain", f"{cs.get('abstain_pct', '–')}%")

        st.markdown("### Top swing shareholders to engage")
        for s in v["top_swing_holders"]:
            st.markdown(f"- **{s.get('holder_name', '—')}**: "
                        f"swing score {s.get('swing_value_score', '–')}, "
                        f"ownership {s.get('ownership_pct', '–')}%")

    with what_t:
        v = views["what"]
        st.subheader(v["subtitle"])

        t = v["thesis"]
        st.markdown(f"### Thesis: **{t.get('name', '—')}**")
        st.markdown(f"- **Power score:** {t.get('score', '–')}/100")
        st.markdown(f"- **Ask:** {t.get('ask', '—')}")
        st.markdown(f"- **Upside:** {t.get('upside', '—')}")
        if t.get("memo"):
            st.markdown("**Activist memo angle:**")
            st.markdown("> " + (t.get("memo") or "").replace("\n", "\n> "))

        st.markdown("### Strongest claims")
        for c in v["strongest_claims"]:
            st.markdown(
                f"- **{c.get('text', '—')}** — power "
                f"{c.get('power', '–')}/100, rebuttability "
                f"{c.get('rebuttability', '–')}"
            )

        d = v["defense_readiness"]
        st.markdown(f"### Defense readiness: **{d.get('score', '–')}/100** "
                    f"— {d.get('level', '—')}")
        if d.get("strongest"):
            st.markdown("**Strongest defenses:**")
            for s in d["strongest"]:
                label = s.get("label", s.get("name", "—")) if isinstance(s, dict) else str(s)
                st.markdown(f"- {label}")
        if d.get("weakest"):
            st.markdown("**Weakest defenses:**")
            for w in d["weakest"]:
                label = w.get("label", w.get("name", "—")) if isinstance(w, dict) else str(w)
                st.markdown(f"- {label}")

        s = v["settle_or_fight"]
        st.markdown(f"### Settle or fight: **{s.get('recommended_path', '—')}**")
        st.markdown(f"- **Best option:** {s.get('best_option', '—')} "
                    f"(utility {s.get('best_utility', '–')}/100)")
        st.markdown(f"- **Runner-up:** {s.get('runner_up', '—')}")

        po = v["proxy_outcomes"]
        st.markdown("### Likely proxy outcomes")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("P(settle)", pct(po.get("p_settle")))
        c2.metric("P(vote)", pct(po.get("p_vote")))
        c3.metric("P(activist ≥1 seat)", pct(po.get("p_activist_wins_1_plus")))
        c4.metric("P(strategic review)", pct(po.get("p_strategic_review")))

        st.markdown("### Top recommended actions")
        for a in v["recommended_actions"]:
            st.markdown(f"- **{a.get('id', '')}: {a.get('name', '—')}** — "
                        f"efficiency {a.get('efficiency', '–')}")

    with when_t:
        v = views["when"]
        st.subheader(v["subtitle"])

        cal = v["calendar"]
        st.markdown("### Calendar")
        c1, c2, c3 = st.columns(3)
        c1.metric("Annual meeting", cal.get("annual_meeting_date", "—"))
        c2.metric("Days until meeting", cal.get("days_to_annual_meeting", "—"))
        c3.metric("Days to nomination deadline",
                  cal.get("days_to_nomination_deadline", "—"))
        if cal.get("nomination_deadline_missed"):
            st.warning("Nomination deadline has passed.")
        c4 = st.columns(1)[0]
        c4.metric("Urgency", f"{cal.get('urgency_score', '–')}/100")

        tr = v["triggers"]
        st.markdown(f"### Active triggers ({tr.get('n_active', 0)})")
        st.markdown(f"**Trigger score:** {tr.get('score', '–')}/100 — "
                    f"urgency: {tr.get('urgency_level', '—')}")
        for t in tr.get("active", []):
            if isinstance(t, dict):
                st.markdown(f"- **{t.get('trigger_type', '—')}**: "
                            f"{t.get('description', '')}")
            else:
                st.markdown(f"- {t}")

        p = v["twelve_month_probabilities"]
        st.markdown("### 12-month probabilities")
        c1, c2, c3 = st.columns(3)
        c1.metric("P(activism event)", pct(p.get("p_activism_event")))
        c2.metric("P(control loss if attacked)", pct(p.get("p_control_loss")))
        c3.metric("P(board seat loss)", pct(p.get("p_board_seat_loss")))

        m = v["expected_market_reaction"]
        st.markdown("### Expected market reaction")
        st.metric("Probability-weighted reaction",
                  f"{m.get('weighted_pp', '–')} pp")
        st.markdown(f"**Risk to stock narrative:** {m.get('narrative', '—')}")

    st.markdown("---")
    st.caption("Switch to **Analyst detail** in the sidebar for the full "
               "16-tab engine output.")
    st.stop()


# view_mode == "Analyst detail (full)" - render the original 16 tabs
# tabs -------------------------------------------------------------------
tabs = st.tabs([
    "1. Executive Overview",
    "2. Vulnerability + Fixability",
    "3. Activist DNA",
    "4. Thesis + Claim Graph",
    "5. Board Vulnerability",
    "6. Nominee Matchup",
    "7. Shareholder Persuasion",
    "8. Swing Shareholders",
    "9. Proxy Advisor Shadow",
    "10. Proxy War Game",
    "11. Fight vs Settle",
    "12. Defense Causal Twin",
    "13. Market Reaction",
    "14. Bank Opportunity",
    "15. War Room",
    "16. Board Memo",
])


# 1 - Executive Overview
with tabs[0]:
    st.header("Executive Overview")
    cols = st.columns(4)
    cols[0].metric("Final Risk Level", risk_level)
    cols[1].metric("Activism Risk Score",
                   f"{float(final.get('activism_risk_score_0_100', 0)):.0f}/100")
    cols[2].metric("P(Activism 12m)",
                   pct(final.get("activism_event_probability_12m")))
    cols[3].metric("Settlement Pressure",
                   f"{float(final.get('settlement_pressure_index', 0)):.0f}/100")

    st.markdown("### Executive Summary")
    st.write(final.get("executive_summary", "(none)"))

    st.markdown("### At-a-Glance Gauges")
    vuln = analysis.get("vulnerability") or {}
    fix = analysis.get("fixability") or {}
    defense = analysis.get("defense") or {}
    bank = analysis.get("bank_opportunity") or {}
    g1, g2, g3, g4 = st.columns(4)
    with g1: st.plotly_chart(gauge(vuln.get("score", 0), "Vulnerability"),
                             use_container_width=True)
    with g2: st.plotly_chart(gauge(fix.get("score", 0), "Fixability"),
                             use_container_width=True)
    with g3: st.plotly_chart(gauge(defense.get("defense_strength_score", 0),
                                    "Defense Strength"),
                             use_container_width=True)
    with g4: st.plotly_chart(gauge(bank.get("mandate_opportunity_score", 0),
                                    "Bank Mandate"),
                             use_container_width=True)

    trig = analysis.get("triggers") or {}
    st.markdown(
        f"### Active Triggers — urgency: **{trig.get('urgency_level', '—')}** "
        f"({trig.get('trigger_score', '–')}/100)"
    )
    active = trig.get("active_triggers") or []
    if active:
        for t in active[:8]:
            if isinstance(t, dict):
                st.markdown(f"- **{t.get('trigger_type', '—')}**: "
                            f"{t.get('description', '')}")
            else:
                st.markdown(f"- {t}")
    else:
        st.write("(no active triggers)")


# 2 - Vulnerability + Fixability
with tabs[1]:
    st.header("Vulnerability & Fixability")
    vuln = analysis.get("vulnerability") or {}
    fix = analysis.get("fixability") or {}
    c1, c2 = st.columns(2)
    with c1:
        st.subheader(f"Vulnerability: {vuln.get('score', '–')}/100 "
                     f"— {vuln.get('level', '—')}")
        st.plotly_chart(component_bar(vuln.get("components") or {},
                                       "Component scores"),
                        use_container_width=True)
        st.markdown("**Top drivers:**")
        for line in (vuln.get("explanation") or [])[:6]:
            st.markdown(f"- {line}")
    with c2:
        st.subheader(f"Fixability: {fix.get('score', '–')}/100 "
                     f"— {fix.get('classification', '—')}")
        st.plotly_chart(component_bar(fix.get("components") or {},
                                       "Fixability components"),
                        use_container_width=True)


# 3 - Activist DNA
with tabs[2]:
    st.header("Activist Archetype Matching (Activist DNA)")
    dna = analysis.get("activist_dna") or []
    top = analysis.get("activist_dna_top") or {}

    if top:
        st.markdown("### Most likely attacker")
        c1, c2, c3 = st.columns(3)
        c1.metric("Archetype", top.get("name", "—"))
        c2.metric("Fit Score", f"{float(top.get('fit_score', 0)):.0f}/100")
        c3.metric("Likely Stake", f"~{top.get('likely_stake_pct', '–')}%")
        st.markdown(f"**Likely campaign style:** {top.get('likely_campaign_style', '—')}")
        st.markdown(f"**Likely board seats requested:** {top.get('likely_board_seats_requested', '—')}")
        st.markdown(f"**Why this archetype:** {top.get('why_this_activist_type', '—')}")

    if dna:
        st.markdown("### Full archetype ranking")
        st.dataframe(pd.DataFrame([{
            "Archetype": d.get("name", "—"),
            "Fit Score": d.get("fit_score", 0),
            "Style": d.get("likely_campaign_style", "—"),
            "Stake %": d.get("likely_stake_pct", "—"),
            "Seats requested": d.get("likely_board_seats_requested", "—"),
        } for d in dna]), use_container_width=True)


# 4 - Thesis + Claim Graph
with tabs[3]:
    st.header("Activist Thesis & Claim Graph")
    primary = analysis.get("primary_thesis") or {}
    theses = analysis.get("theses") or []

    st.markdown(f"### Primary thesis: **{primary.get('name', '—')}** "
                f"({primary.get('score', '–')}/100)")
    st.markdown(f"- **Recommended ask:** {primary.get('recommended_ask', '—')}")
    st.markdown(f"- **Estimated upside:** {primary.get('estimated_upside_range', '—')}")
    st.markdown("**Attack memo:**")
    st.markdown("> " + primary.get("activist_attack_memo", "—").replace("\n", "\n> "))

    if theses:
        st.markdown("### All theses ranked")
        st.dataframe(pd.DataFrame([{
            "Thesis": t.get("name", "—"),
            "Score": t.get("score", 0),
            "Ask": t.get("recommended_ask", "—"),
            "Upside": t.get("estimated_upside_range", "—"),
        } for t in theses]), use_container_width=True)

    cg = analysis.get("claim_graph") or {}
    st.markdown("### Strongest claims (activist will use)")
    for c in (cg.get("strongest_claims") or [])[:6]:
        st.markdown(
            f"- **{c.get('claim_text', c.get('claim', '—'))}** "
            f"— power {c.get('claim_power_score', '–')}/100, "
            f"rebuttability {c.get('rebuttability', '–')}"
        )

    att = analysis.get("claim_attack_table") or []
    if att:
        st.markdown("### Attack vs Defense table")
        st.dataframe(pd.DataFrame(att), use_container_width=True)


# 5 - Board Vulnerability
with tabs[4]:
    st.header("Board Vulnerability Map")
    director_scores = analysis.get("director_scores") or []
    if not director_scores:
        st.write("(no director scoring data)")
    else:
        ranked = sorted(director_scores,
                        key=lambda x: -float(x.get("score", 0) or 0))
        st.dataframe(pd.DataFrame([{
            "Director": d.get("name", "—"),
            "Score": d.get("score", 0),
            "Risk": d.get("risk_level", "—"),
            "Tenure (y)": d.get("tenure_years", "—"),
            "Independent": d.get("independent", "—"),
            "Committee chair": d.get("is_committee_chair", "—"),
            "Prior vote %": d.get("prior_vote_support_pct", "—"),
            "Top reason": (d.get("top_reasons") or ["—"])[0]
                          if d.get("top_reasons") else "—",
        } for d in ranked]), use_container_width=True)

        st.markdown("### Highest-risk directors")
        for d in ranked[:3]:
            with st.expander(f"{d.get('name','—')} — {d.get('score','–')}/100 "
                             f"({d.get('risk_level','—')})"):
                st.markdown(f"**Best activist attack angle:** "
                            f"{d.get('best_activist_attack_angle','—')}")
                st.markdown(f"**Replacement profile:** "
                            f"{d.get('recommended_replacement_profile','—')}")
                st.markdown("**Top reasons:**")
                for r in (d.get("top_reasons") or [])[:4]:
                    st.markdown(f"- {r}")


# 6 - Nominee Matchup
with tabs[5]:
    st.header("Nominee Matchup Optimizer")
    slate = analysis.get("slate") or {}
    rec = slate.get("recommended_slate") or slate.get("slate") or []
    st.markdown(f"### Recommended activist slate (size {len(rec)})")
    if rec:
        st.dataframe(pd.DataFrame(rec), use_container_width=True)

    profs = analysis.get("nominee_profiles") or []
    if profs:
        st.markdown("### Full nominee profile library")
        st.dataframe(pd.DataFrame([{
            "Profile": n.get("profile_name", "—"),
            "Stature": n.get("stature_score", "—"),
            "PA Appeal": n.get("proxy_advisor_appeal", "—"),
            "Shareholder credibility": n.get("shareholder_credibility", "—"),
        } for n in profs]), use_container_width=True)


# 7 - Shareholder Persuasion
with tabs[6]:
    st.header("Shareholder Coalition")
    coalition = analysis.get("coalition") or {}

    c1, c2, c3 = st.columns(3)
    c1.metric("Activist coalition",
              f"{coalition.get('expected_activist_vote_pct', '–')}%")
    c2.metric("Management coalition",
              f"{coalition.get('expected_management_vote_pct', '–')}%")
    c3.metric("Abstain", f"{coalition.get('expected_abstain_pct', '–')}%")

    by_type = coalition.get("by_holder_type") or {}
    if by_type:
        rows = []
        for k, v in by_type.items():
            if isinstance(v, dict):
                rows.append({
                    "Holder type": k,
                    "Activist support %": v.get("activist_support_pct", "—"),
                    "Ownership %": v.get("ownership_pct", "—"),
                })
        if rows:
            st.markdown("### Activist support by holder type")
            df = pd.DataFrame(rows).sort_values("Activist support %",
                                                ascending=False)
            st.dataframe(df, use_container_width=True)
            fig = px.bar(df, x="Holder type", y="Activist support %",
                         color="Activist support %",
                         color_continuous_scale="RdYlGn_r")
            st.plotly_chart(fig, use_container_width=True)


# 8 - Swing Shareholders
with tabs[7]:
    st.header("Swing Shareholders — Priority Outreach")
    sw = analysis.get("swing_shareholders") or {}
    top5 = sw.get("top_5_priority_outreach") or []
    if top5:
        st.markdown("### Top-5 priority targets")
        for s in top5:
            with st.expander(f"{s.get('holder_name','—')} — swing score "
                             f"{s.get('swing_value_score', '–')}"):
                st.markdown(f"- Ownership: {s.get('ownership_pct', '–')}%")
                st.markdown(f"- Holder type: {s.get('holder_type', '—')}")
                st.markdown(f"- Outreach: {s.get('outreach_recommendation', '—')}")

    swing_list = sw.get("swing_holders") or sw.get("ranked_holders") or []
    if swing_list:
        st.markdown("### Full swing-shareholder ranking")
        st.dataframe(pd.DataFrame(swing_list), use_container_width=True)


# 9 - Proxy Advisor Shadow
with tabs[8]:
    st.header("Proxy Advisor Shadow Report (ISS / Glass Lewis)")
    pa = analysis.get("proxy_advisor") or {}
    c1, c2 = st.columns(2)
    c1.metric("P(support mgmt full slate)",
              pct(pa.get("p_support_management_full_slate")))
    c2.metric("P(support 1 activist nominee)",
              pct(pa.get("p_support_one_activist_nominee")))
    c1.metric("P(support 2+ activist nominees)",
              pct(pa.get("p_support_two_plus_activist_nominees")))
    c2.metric("P(against say-on-pay)",
              pct(pa.get("p_recommend_against_pay")))

    st.markdown(f"**PA governance concern score:** "
                f"{pa.get('pa_governance_concern_score', '–')}/100")
    if pa.get("specific_director_at_risk"):
        st.warning(f"Director-specific risk: {pa.get('specific_director_at_risk')}")

    if pa.get("key_drivers"):
        st.markdown("**Key drivers of PA stance:**")
        for d in pa.get("key_drivers"):
            st.markdown(f"- {d}")

    if pa.get("recommended_preemptive_steps"):
        st.markdown("**Recommended pre-emptive steps:**")
        for s in pa.get("recommended_preemptive_steps"):
            st.markdown(f"- {s}")


# 10 - Proxy War Game
with tabs[9]:
    st.header("Proxy Contest Monte Carlo Simulation")
    sim = analysis.get("simulation") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P(private settlement)", pct(sim.get("p_private_settlement")))
    c2.metric("P(proxy vote)", pct(sim.get("p_proxy_vote")))
    c3.metric("P(activist wins ≥1 seat)", pct(sim.get("p_activist_wins_1_plus")))
    c4.metric("P(activist wins ≥2 seats)", pct(sim.get("p_activist_wins_2_plus")))

    st.markdown(f"**Interpretation:** {sim.get('interpretation','—')}")

    counts = sim.get("scenario_counts") or {}
    if counts:
        df = pd.DataFrame([{"Scenario": k, "Count": v} for k, v in counts.items()])
        df = df[df["Count"] > 0].sort_values("Count", ascending=False)
        if len(df):
            fig = px.bar(df, x="Scenario", y="Count",
                         title="Scenario distribution")
            fig.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

    sens = sim.get("sensitivity") or {}
    if sens:
        st.markdown("### Sensitivity analysis (one-input flexes)")
        st.dataframe(pd.DataFrame(
            [{"Flex": label, **vals} for label, vals in sens.items()]
        ), use_container_width=True)


# 11 - Fight vs Settle
with tabs[10]:
    st.header("Settlement Game Theory")
    settlement = analysis.get("settlement") or {}
    st.markdown(f"### Recommended path: **{settlement.get('recommended_path', '—')}**")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Best option")
        st.write(settlement.get("best_option") or {})
    with c2:
        st.markdown("#### Runner-up")
        st.write(settlement.get("runner_up_option") or {})

    options = settlement.get("options") or []
    if options:
        st.markdown("### All options ranked")
        st.dataframe(pd.DataFrame(options), use_container_width=True)

    st.markdown("### Suggested negotiation script")
    st.text_area("Script", settlement.get("negotiation_script", "—"), height=200)


# 12 - Defense Causal Twin
with tabs[11]:
    st.header("Defense Causal Twin")
    ct = analysis.get("causal_twin") or {}
    pkg = analysis.get("defense_package") or {}

    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline risk",
              f"{float(pkg.get('estimated_risk_before', 0)):.0f}")
    c2.metric("After defense package",
              f"{float(pkg.get('estimated_risk_after', 0)):.0f}")
    c3.metric("Δ Risk",
              f"-{float(pkg.get('estimated_risk_reduction', 0)):.0f}")

    rec = pkg.get("recommended_actions") or []
    if rec:
        st.markdown("### Recommended actions")
        st.dataframe(pd.DataFrame(rec), use_container_width=True)

    plan = pkg.get("ninety_day_plan") or []
    if plan:
        st.markdown("### 90-day execution plan")
        if isinstance(plan, list):
            st.dataframe(pd.DataFrame(plan), use_container_width=True)
        else:
            for k, v in plan.items():
                st.markdown(f"**{k}:** {v}")

    if ct.get("delta_vs_baseline"):
        st.markdown("### Causal twin: predicted state changes")
        st.json(ct.get("delta_vs_baseline"))
    if ct.get("best_combined_package"):
        st.markdown("### Best combined package (with interactions)")
        st.json(ct.get("best_combined_package"))


# 13 - Market Reaction
with tabs[12]:
    st.header("Expected Market Reaction")
    mr = analysis.get("market_reaction") or {}

    st.metric("Probability-weighted expected reaction",
              f"{mr.get('expected_reaction_weighted_pp', '–')} pp")
    st.markdown(f"**Risk to stock narrative:** {mr.get('risk_to_stock_story', '—')}")

    scenarios = mr.get("scenario_reactions") or {}
    weights = mr.get("scenario_weights") or {}
    if scenarios:
        rows = []
        for k, v in scenarios.items():
            if isinstance(v, dict):
                rows.append({
                    "Scenario": k,
                    "Expected (pp)": v.get("expected_reaction_pp", "—"),
                    "P10": v.get("p10", "—"),
                    "P90": v.get("p90", "—"),
                    "Weight": weights.get(k, "—"),
                    "Narrative": v.get("narrative", "—"),
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)


# 14 - Bank Opportunity
with tabs[13]:
    st.header("Bank / Advisory Mandate Opportunity")
    bo = analysis.get("bank_opportunity") or {}
    c1, c2 = st.columns(2)
    c1.metric("Mandate opportunity score",
              f"{float(bo.get('mandate_opportunity_score', 0)):.0f}/100")
    c2.metric("Opportunity level", bo.get("opportunity_level", "—"))

    st.markdown(f"**Pitch angle:** {bo.get('banker_pitch_angle', '—')}")
    st.markdown("### Likely advisory products")
    for p in (bo.get("likely_advisory_products") or [])[:6]:
        if isinstance(p, dict):
            st.markdown(f"- **{p.get('product', p.get('name', '—'))}** "
                        f"— {p.get('rationale', p.get('description', ''))}")
        else:
            st.markdown(f"- {p}")

    st.markdown("### Suggested client email")
    st.text_area("Email", bo.get("suggested_client_email", "—"), height=240)
    st.markdown("### Board-meeting pitch summary")
    st.markdown(bo.get("board_meeting_pitch_summary", "—"))


# 15 - War Room
with tabs[14]:
    st.header("War Room")
    wr = analysis.get("war_room") or {}

    sub_tabs = st.tabs(["Red Team Attack", "Blue Team Defense",
                        "Board Q&A", "Investor Talking Points",
                        "Press Statement"])
    with sub_tabs[0]:
        st.markdown(wr.get("red_team_attack", "(none)"))
    with sub_tabs[1]:
        st.markdown(wr.get("blue_team_defense", "(none)"))
    with sub_tabs[2]:
        for qa in (wr.get("board_qa") or []):
            with st.expander(qa.get("q", "—")):
                st.write(qa.get("a", "—"))
    with sub_tabs[3]:
        for tp in (wr.get("investor_talking_points") or []):
            st.markdown(f"- {tp}")
    with sub_tabs[4]:
        st.markdown(wr.get("press_narrative", "(none)"))


# 16 - Board Memo
with tabs[15]:
    st.header("Board Briefing Memo")
    memo = analysis.get("board_memo") or "(memo unavailable)"
    st.download_button(
        "Download board memo (Markdown)",
        memo,
        file_name=f"{company.get('ticker', 'company')}_board_memo.md",
        mime="text/markdown",
    )
    st.markdown(memo)


# footer -----------------------------------------------------------------
st.markdown("---")
st.caption(f"{COMPLIANCE_NOTE} All data synthetic; for demonstration only.")
