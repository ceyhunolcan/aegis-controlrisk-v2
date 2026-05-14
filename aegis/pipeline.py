# The central orchestrator. Every consumer - the Streamlit app, smoke test,
# memo writer, backtest, unit tests - calls run_company_analysis() and reads
# from the dict it returns. Adding a new view = adding a new consumer, not a
# new entry point.
#
# CASCADE-2 pipeline architecture is proprietary IP. Copyright (c) 2026.
# Source-available under a proprietary license. See LICENSE / COMMERCIAL.md.
#
# The pipeline runs ~32 steps in a specific order. The non-obvious dependency:
# director scoring has to happen BEFORE the claim graph, because claims about
# specific directors reference the per-director vulnerability scores. And we
# run the Monte Carlo twice - once with a placeholder settlement_pressure,
# then again with the real value after the preliminary final score has
# computed it. Yes it's a little annoying, no I haven't found a cleaner way
# that doesn't introduce a circular import.
from datetime import date

from .scoring.vulnerability import score_vulnerability
from .scoring.fixability import score_fixability
from .scoring.activist_dna import rank_activist_archetypes
from .scoring.thesis import generate_theses, select_primary_thesis
from .scoring.directors import score_all_directors
from .scoring.nominee_matchup import optimize_activist_slate, generate_nominee_profiles
from .scoring.claim_graph import (
    build_claim_graph,
    generate_claim_level_attack_table,
    generate_claim_level_defense_table,
)
from .scoring.shareholders import build_shareholder_graph, estimate_shareholder_coalition
from .scoring.swing_shareholders import identify_swing_shareholders
from .scoring.legal_calendar import analyze_legal_calendar
from .scoring.trigger_monitor import analyze_triggers
from .scoring.proxy_advisor_shadow import simulate_proxy_advisor_view
from .scoring.defense import simulate_management_defense
from .scoring.settlement_game import evaluate_settlement_options
from .scoring.final_score import calculate_final_controlrisk_score
from .scoring.bank_opportunity import score_bank_mandate_opportunity
from .simulation.proxy_monte_carlo import run_proxy_monte_carlo
from .simulation.counterfactuals import optimize_defense_package, generate_defense_actions
from .simulation.causal_twin import run_causal_defense_twin
from .simulation.market_reaction import simulate_market_reaction


def _records_for_company(df, company_id):
    if df is None or len(df) == 0:
        return []
    try:
        return df[df["company_id"].astype(str) == str(company_id)].to_dict("records")
    except Exception:
        return []


def _all_records(df):
    if df is None:
        return []
    try:
        return df.to_dict("records")
    except Exception:
        return []


def run_company_analysis(company_id, data, as_of_date=None):
    """Run the full CASCADE-2 analysis for one company.

    `data` is the dict returned by aegis.data.loader.load_all_data().
    Returns a single dict containing every output the dashboard/memo/etc need.
    """
    if as_of_date is None:
        as_of_date = date.today()

    if company_id is None:
        raise ValueError("company_id is required (got None)")
    company_id = str(company_id).strip()
    data = data or {}

    # resolve company + financials.
    # NOTE: the try/except wraps pandas indexing because malformed input
    # (missing `company_id` column, all-NaN column, etc.) shouldn't crash
    # the whole pipeline. We re-raise on AttributeError/ImportError because
    # those mean someone passed a non-DataFrame and we want that loud.
    companies_df = data.get("companies")
    company_row = {}
    if companies_df is not None and len(companies_df) > 0:
        try:
            sub = companies_df[companies_df["company_id"].astype(str) == company_id]
            if len(sub):
                company_row = sub.iloc[0].to_dict()
        except (KeyError, ValueError, TypeError) as e:
            import warnings
            warnings.warn(f"pipeline: company lookup failed for {company_id!r}: {e}")

    fin_df = data.get("financials")
    financials = {}
    if fin_df is not None and len(fin_df) > 0:
        try:
            sub = fin_df[fin_df["company_id"].astype(str) == company_id]
            if len(sub):
                financials = sub.iloc[0].to_dict()
        except (KeyError, ValueError, TypeError) as e:
            import warnings
            warnings.warn(f"pipeline: financials lookup failed for {company_id!r}: {e}")

    directors    = _records_for_company(data.get("directors"), company_id)
    shareholders = _all_records(data.get("shareholders"))  # universe, not filtered
    ownerships   = _records_for_company(data.get("ownership"), company_id)
    events       = _records_for_company(data.get("events"), company_id)
    campaigns    = _all_records(data.get("campaigns"))     # used as truth for backtest
    archetypes   = _all_records(data.get("activist_archetypes"))
    pa_cases     = _all_records(data.get("proxy_advisor_cases"))
# core scoring
    vulnerability = score_vulnerability(company_row, financials)
    fixability    = score_fixability(company_row, financials)
    legal         = analyze_legal_calendar(company_row, as_of_date=as_of_date)
    triggers      = analyze_triggers(company_row, events, legal, as_of_date=as_of_date)

    # who is likely to attack, what they're likely to say
    activist_dna     = rank_activist_archetypes(company_row, financials, vulnerability, fixability, archetypes)
    activist_dna_top = activist_dna[0] if activist_dna else None
    theses           = generate_theses(company_row, financials, vulnerability, fixability, activist_dna)
    primary_thesis   = select_primary_thesis(theses)

    # directors must be scored BEFORE the claim graph
    director_scores  = score_all_directors(directors, company_row, financials)
    nominee_profiles = generate_nominee_profiles()
    slate            = optimize_activist_slate(director_scores, company_row, max_slate_size=3)

    claim_graph         = build_claim_graph(company_row, primary_thesis, vulnerability, fixability, director_scores)
    claim_attack_table  = generate_claim_level_attack_table(claim_graph)
    claim_defense_table = generate_claim_level_defense_table(claim_graph)

    # holders + coalition
    shareholder_graph = build_shareholder_graph(company_row, shareholders, ownerships, vulnerability, primary_thesis)
    holder_estimates  = shareholder_graph.get("holders", [])
    coalition         = estimate_shareholder_coalition(holder_estimates, company_row)
    swing             = identify_swing_shareholders(holder_estimates, coalition)

    proxy_advisor = simulate_proxy_advisor_view(
        company_row, financials, primary_thesis, director_scores, vulnerability, fixability,
    )
    defense = simulate_management_defense(
        company_row, financials, primary_thesis, claim_graph, director_scores,
        proxy_advisor, vulnerability,
    )

    # First MC pass with a placeholder; we'll refine after final_score gives us
    # the real settlement pressure index.
    simulation = run_proxy_monte_carlo(
        coalition, director_scores, proxy_advisor, defense, settlement_pressure=50.0,
    )

    settlement = evaluate_settlement_options(
        company_row, primary_thesis, director_scores, coalition,
        proxy_advisor, simulation, defense,
    )

    defense_actions = generate_defense_actions()
    defense_package = optimize_defense_package(
        actions=defense_actions,
        company=company_row,
        vulnerability=vulnerability,
        pa_view=proxy_advisor,
        initial_risk_score=float(vulnerability.get("score", 50)),
        max_actions=5,
    )

    # Preliminary final score - we need the settlement_pressure_index out
    # of this to refine the MC.
    final_prelim = calculate_final_controlrisk_score(
        company_row, vulnerability, fixability, legal, triggers, coalition,
        proxy_advisor, simulation, defense, settlement, primary_thesis, activist_dna_top,
    )
    settlement_pressure = final_prelim.get("settlement_pressure_index", 50.0)

    chosen_actions = [a["action_id"] for a in defense_package.get("recommended_actions", [])]
    causal_twin = run_causal_defense_twin(
        chosen_actions, vulnerability, primary_thesis, director_scores,
        coalition, proxy_advisor, final_prelim,
        settlement_pressure=settlement_pressure,
    )

    # MC pass 2 - now with the real settlement_pressure
    simulation_refined = run_proxy_monte_carlo(
        coalition, director_scores, proxy_advisor, defense,
        settlement_pressure=settlement_pressure,
    )

    market_reaction = simulate_market_reaction(
        company_row, vulnerability, fixability, primary_thesis, simulation_refined,
    )

    # Final score recomputed on the refined sim
    final_score = calculate_final_controlrisk_score(
        company_row, vulnerability, fixability, legal, triggers, coalition,
        proxy_advisor, simulation_refined, defense, settlement, primary_thesis, activist_dna_top,
    )

    bank_opportunity = score_bank_mandate_opportunity(
        company_row, final_score, vulnerability, fixability, legal,
        triggers, settlement, defense,
    )

    analysis = {
        "company_id": company_id,
        "company": company_row,
        "financials": financials,
        "directors": directors,
        "shareholders": shareholders,
        "ownerships": ownerships,
        "events": events,
        "campaigns": campaigns,
        "archetypes": archetypes,
        "proxy_advisor_cases": pa_cases,
        "vulnerability": vulnerability,
        "fixability": fixability,
        "legal": legal,
        "triggers": triggers,
        "activist_dna": activist_dna,
        "activist_dna_top": activist_dna_top,
        "theses": theses,
        "primary_thesis": primary_thesis,
        "director_scores": director_scores,
        "nominee_profiles": nominee_profiles,
        "slate": slate,
        "claim_graph": claim_graph,
        "claim_attack_table": claim_attack_table,
        "claim_defense_table": claim_defense_table,
        "shareholder_graph": shareholder_graph,
        "coalition": coalition,
        "swing_shareholders": swing,
        "proxy_advisor": proxy_advisor,
        "defense": defense,
        "simulation": simulation_refined,
        "settlement": settlement,
        "defense_actions": defense_actions,
        "defense_package": defense_package,
        "causal_twin": causal_twin,
        "market_reaction": market_reaction,
        "final_score": final_score,
        "bank_opportunity": bank_opportunity,
        "board_memo": "",
        "war_room": {},
    }

    # Memo + war room are filled last because they consume everything above.
    # Imported locally to avoid an import cycle through reports/.
    try:
        from .reports.memo_generator import generate_board_memo
        analysis["board_memo"] = generate_board_memo(analysis)
    except Exception as e:
        analysis["board_memo"] = f"[Board memo generation error: {e}]"

    try:
        from .reports.war_room import generate_war_room_outputs
        analysis["war_room"] = generate_war_room_outputs(analysis)
    except Exception as e:
        analysis["war_room"] = {"error": f"War room generation error: {e}"}

    # Confidence bands + provenance. These are additive - any consumer
    # that doesn't care about them just ignores the keys. We put them
    # last so a failure here can't break the headline outputs.
    try:
        from .audit.confidence_bands import confidence_bands_for_simulation
        analysis["confidence_bands"] = confidence_bands_for_simulation(
            simulation_refined
        )
    except Exception as e:
        analysis["confidence_bands"] = {"error": str(e)}

    try:
        from .audit.provenance import make_provenance, attach_provenance
        # Vulnerability provenance is the most useful one - it's the score
        # boards push back on most.
        from .scoring.vulnerability import WEIGHTS as _VULN_WEIGHTS
        prov = make_provenance(
            score_name="vulnerability",
            score_value=vulnerability.get("score"),
            components=vulnerability.get("components"),
            weights=_VULN_WEIGHTS,
            inputs={
                k: financials.get(k) for k in (
                    "tsr_3y_vs_peer", "ev_ebitda_discount_vs_peer",
                    "roic_gap_vs_peer", "say_on_pay_support_pct",
                ) if k in financials
            },
            data_sources=[("financials", "synthetic")],
        )
        attach_provenance(analysis, "vulnerability", prov)
    except Exception:
        pass

    return analysis
