# Layer-2 dashboard views. Three question-shaped pages instead of 16
# engine-shaped tabs.
#
# Who:  who's likely to come after us, what kind of fund, with what stake,
#       and which directors do they target?
# What: what's the thesis they'll run, what claims will they make, what
#       defense holds up, what's the settle-vs-fight call?
# When: nomination deadlines, annual meeting, active triggers, scenario
#       probability over the next 12 months.
#
# Each function returns a dict the dashboard renders. The structure is
# stable so the frontend can iterate without breaking the data contract.


def who_view(analysis):
    """Who is likely to attack + which directors are exposed."""
    dna = analysis.get("activist_dna_top") or {}
    director_scores = analysis.get("director_scores") or []
    slate = analysis.get("slate") or {}
    coalition = analysis.get("coalition") or {}
    swing = analysis.get("swing_shareholders") or {}

    ranked_dirs = sorted(
        director_scores, key=lambda d: -float(d.get("score", 0) or 0)
    )

    return {
        "section_title": "Who",
        "subtitle": "Likely attacker, target directors, swing shareholders",
        "attacker": {
            "archetype": dna.get("name"),
            "fit_score": dna.get("fit_score"),
            "style": dna.get("likely_campaign_style"),
            "likely_stake_pct": dna.get("likely_stake_pct"),
            "likely_seats_requested": dna.get("likely_board_seats_requested"),
            "rationale": dna.get("why_this_activist_type"),
        },
        "high_risk_directors": [
            {
                "name": d.get("name"),
                "score": d.get("score"),
                "risk_level": d.get("risk_level"),
                "best_attack_angle": d.get("best_activist_attack_angle"),
                "replacement_profile": d.get("recommended_replacement_profile"),
            }
            for d in ranked_dirs[:3]
        ],
        "recommended_slate": (
            slate.get("recommended_slate") or slate.get("slate") or []
        )[:3],
        "coalition_summary": {
            "activist_pct": coalition.get("expected_activist_vote_pct"),
            "management_pct": coalition.get("expected_management_vote_pct"),
            "abstain_pct": coalition.get("expected_abstain_pct"),
        },
        "top_swing_holders": (swing.get("top_5_priority_outreach") or [])[:3],
    }


def what_view(analysis):
    """What thesis, what claims, what defense, settle vs fight."""
    primary = analysis.get("primary_thesis") or {}
    claim_graph = analysis.get("claim_graph") or {}
    defense = analysis.get("defense") or {}
    settlement = analysis.get("settlement") or {}
    sim = analysis.get("simulation") or {}
    defense_pkg = analysis.get("defense_package") or {}

    return {
        "section_title": "What",
        "subtitle": "Thesis, claims, defense readiness, settle vs fight",
        "thesis": {
            "name": primary.get("name"),
            "score": primary.get("score"),
            "ask": primary.get("recommended_ask"),
            "upside": primary.get("estimated_upside_range"),
            "memo": primary.get("activist_attack_memo"),
        },
        "strongest_claims": [
            {
                "text": c.get("claim_text") or c.get("claim"),
                "power": c.get("claim_power_score"),
                "rebuttability": c.get("rebuttability"),
            }
            for c in (claim_graph.get("strongest_claims") or [])[:5]
        ],
        "defense_readiness": {
            "score": defense.get("defense_strength_score"),
            "level": defense.get("defense_level"),
            "strongest": (defense.get("strongest_defenses") or [])[:3],
            "weakest": (defense.get("weakest_defenses") or [])[:3],
        },
        "settle_or_fight": {
            "recommended_path": settlement.get("recommended_path"),
            "best_option": (settlement.get("best_option") or {}).get("option_name"),
            "best_utility": (settlement.get("best_option") or {}).get("utility_score"),
            "runner_up": (settlement.get("runner_up_option") or {}).get("option_name"),
        },
        "proxy_outcomes": {
            "p_settle": sim.get("p_private_settlement"),
            "p_vote": sim.get("p_proxy_vote"),
            "p_activist_wins_1_plus": sim.get("p_activist_wins_1_plus"),
            "p_strategic_review": sim.get("p_strategic_review"),
        },
        "recommended_actions": [
            {
                "id": a.get("action_id"),
                "name": a.get("action_name"),
                "efficiency": a.get("efficiency_score"),
            }
            for a in (defense_pkg.get("recommended_actions") or [])[:5]
        ],
    }


def when_view(analysis):
    """When: calendar, triggers, time-decayed scenarios."""
    legal = analysis.get("legal") or {}
    triggers = analysis.get("triggers") or {}
    final = analysis.get("final_score") or {}
    sim = analysis.get("simulation") or {}
    market = analysis.get("market_reaction") or {}

    return {
        "section_title": "When",
        "subtitle": "Calendar pressure, active triggers, scenario timeline",
        "calendar": {
            "annual_meeting_date": legal.get("annual_meeting_date"),
            "days_to_annual_meeting": legal.get("days_to_annual_meeting"),
            "nomination_deadline": legal.get("nomination_deadline"),
            "days_to_nomination_deadline": legal.get("days_to_nomination_deadline"),
            "nomination_deadline_missed": legal.get("deadline_missed"),
            "urgency_score": legal.get("urgency_score"),
        },
        "triggers": {
            "score": triggers.get("trigger_score"),
            "urgency_level": triggers.get("urgency_level"),
            "n_active": triggers.get("n_triggers"),
            "active": (triggers.get("active_triggers") or [])[:5],
        },
        "twelve_month_probabilities": {
            "p_activism_event": final.get("activism_event_probability_12m"),
            "p_control_loss": final.get("control_loss_probability_if_attacked"),
            "p_board_seat_loss": final.get("board_seat_loss_probability"),
            "p_activist_wins_1_plus_in_proxy": sim.get("p_activist_wins_1_plus"),
        },
        "expected_market_reaction": {
            "weighted_pp": market.get("expected_reaction_weighted_pp"),
            "narrative": market.get("risk_to_stock_story"),
        },
    }


def all_layer2_views(analysis):
    """Convenience: all three views in one call."""
    return {
        "who": who_view(analysis),
        "what": what_view(analysis),
        "when": when_view(analysis),
    }
