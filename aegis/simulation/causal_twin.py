# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# "Causal twin": apply a set of defense actions to the baseline model state
# and predict the resulting shifts. The deltas in ACTION_EFFECTS are tuned
# from a mix of literature and gut feel - happy to take feedback on them.
#
# Two-pair interaction effects in INTERACTIONS capture the cases where
# combining actions matters more (or less) than the sum of parts. E.g.
# DA01 + DA05 (refresh board + capalloc framework) is greater-than-sum
# because the new board members signal real change, not box-checking.
from ..utils.normalization import clamp, safe_float, probability_clamp


# Per-action delta table. Keys are downstream model variables that the
# pipeline already produces; sign convention: negative = good for the company.
ACTION_EFFECTS = {
    "DA01": {  # Refresh 1-2 seats
        "vulnerability": -6, "thesis_power": -7, "director_replaceability_avg": -10,
        "expected_activist_vote_pct": -4, "p_against_specific_director": -0.10,
        "board_seat_loss_p": -0.08, "settlement_pressure_index": -10,
    },
    "DA02": {  # Declassify
        "vulnerability": -3, "thesis_power": -5, "director_replaceability_avg": 0,
        "expected_activist_vote_pct": -2, "p_against_specific_director": -0.05,
        "board_seat_loss_p": 0.02,  # easier for activist to win but lower thesis power
        "settlement_pressure_index": -5,
    },
    "DA03": {  # Separate Chair
        "vulnerability": -3, "thesis_power": -4, "director_replaceability_avg": -3,
        "expected_activist_vote_pct": -2, "p_against_specific_director": -0.06,
        "board_seat_loss_p": -0.02, "settlement_pressure_index": -5,
    },
    "DA04": {  # Majority voting
        "vulnerability": -2, "thesis_power": -2, "director_replaceability_avg": 0,
        "expected_activist_vote_pct": -1, "p_against_specific_director": -0.03,
        "board_seat_loss_p": 0.01, "settlement_pressure_index": -3,
    },
    "DA05": {  # Capital allocation framework
        "vulnerability": -6, "thesis_power": -8, "director_replaceability_avg": -2,
        "expected_activist_vote_pct": -3, "p_against_specific_director": -0.04,
        "board_seat_loss_p": -0.04, "settlement_pressure_index": -8,
    },
    "DA06": {  # Buyback / dividend
        "vulnerability": -4, "thesis_power": -5, "director_replaceability_avg": -1,
        "expected_activist_vote_pct": -3, "p_against_specific_director": -0.02,
        "board_seat_loss_p": -0.03, "settlement_pressure_index": -6,
    },
    "DA07": {  # Strategic review
        "vulnerability": -6, "thesis_power": -10, "director_replaceability_avg": -2,
        "expected_activist_vote_pct": -5, "p_against_specific_director": -0.04,
        "board_seat_loss_p": -0.05, "settlement_pressure_index": -12,
    },
    "DA08": {  # Top-25 holder engagement
        "vulnerability": -2, "thesis_power": -3, "director_replaceability_avg": -1,
        "expected_activist_vote_pct": -5, "p_against_specific_director": -0.04,
        "board_seat_loss_p": -0.06, "settlement_pressure_index": -7,
    },
    "DA09": {  # Compensation reset
        "vulnerability": -4, "thesis_power": -4, "director_replaceability_avg": -3,
        "expected_activist_vote_pct": -2, "p_against_specific_director": -0.08,
        "board_seat_loss_p": -0.02, "settlement_pressure_index": -5,
    },
    "DA10": {  # ESG plan
        "vulnerability": -3, "thesis_power": -4, "director_replaceability_avg": -1,
        "expected_activist_vote_pct": -3, "p_against_specific_director": -0.02,
        "board_seat_loss_p": -0.03, "settlement_pressure_index": -4,
    },
    "DA11": {  # Poison pill
        "vulnerability": 1, "thesis_power": 3, "director_replaceability_avg": 0,
        "expected_activist_vote_pct": -1, "p_against_specific_director": 0.02,
        "board_seat_loss_p": -0.10, "settlement_pressure_index": -4,
    },
    "DA12": {  # PA pre-engagement
        "vulnerability": -2, "thesis_power": -3, "director_replaceability_avg": -1,
        "expected_activist_vote_pct": -3, "p_against_specific_director": -0.08,
        "board_seat_loss_p": -0.05, "settlement_pressure_index": -6,
    },
}


# Interaction effects: pairs that have non-additive lift
INTERACTIONS = {
    ("DA01", "DA05"): {"vulnerability": -3, "settlement_pressure_index": -4,
                       "note": "Board refresh + capital allocation framework: more credible than either alone."},
    ("DA02", "DA03"): {"vulnerability": -2, "settlement_pressure_index": -3,
                       "note": "Declassify + chair separation: comprehensive governance reset."},
    ("DA08", "DA12"): {"vulnerability": -2, "settlement_pressure_index": -3,
                       "note": "Top-25 engagement + PA pre-engagement: hits both buy-side and proxy advisor channels."},
    ("DA05", "DA09"): {"vulnerability": -2, "settlement_pressure_index": -3,
                       "note": "Capital framework + compensation alignment: addresses two top proxy advisor lenses."},
    ("DA07", "DA08"): {"vulnerability": -3, "settlement_pressure_index": -4,
                       "note": "Strategic review + shareholder engagement: pre-empts strategic-alternatives activism."},
}


def simulate_defense_action_effects(action_id, baseline):
    """Apply a single action's deltas to a baseline state."""
    effects = ACTION_EFFECTS.get(action_id, {})
    new_state = dict(baseline)
    for k, dv in effects.items():
        cur = safe_float(new_state.get(k, 0), 0)
        new_state[k] = cur + dv
    return {"action_id": action_id, "deltas": effects, "post_state": new_state}


def _baseline_from_inputs(vulnerability, primary_thesis, director_scores,
                          coalition, pa_view, final_score, settlement_pressure):
    avg_dir = 50.0
    if director_scores:
        avg_dir = sum(safe_float(d.get("score", 50), 50) for d in director_scores) / len(director_scores)
    return {
        "vulnerability": safe_float(vulnerability.get("score", 50), 50) if vulnerability else 50,
        "thesis_power": safe_float(primary_thesis.get("score", 50), 50) if primary_thesis else 50,
        "director_replaceability_avg": avg_dir,
        "expected_activist_vote_pct": safe_float(coalition.get("expected_activist_vote_pct", 35), 35) if coalition else 35,
        "p_against_specific_director": safe_float(pa_view.get("p_recommend_against_specific_director", 0.3), 0.3) if pa_view else 0.3,
        "board_seat_loss_p": safe_float(final_score.get("board_seat_loss_probability", 0.3), 0.3) if final_score else 0.3,
        "settlement_pressure_index": float(settlement_pressure),
    }


def run_causal_defense_twin(
    actions,
    vulnerability,
    primary_thesis,
    director_scores,
    coalition,
    pa_view,
    final_score,
    settlement_pressure = 50.0):
    """Simulate combined effects of multiple defense actions, including interactions."""
    if not actions:
        actions = list(ACTION_EFFECTS.keys())[:5]

    baseline = _baseline_from_inputs(vulnerability, primary_thesis, director_scores,
                                      coalition, pa_view, final_score, settlement_pressure)

    # Action-by-action
    action_effects = []
    for aid in actions:
        sim = simulate_defense_action_effects(aid, baseline)
        action_effects.append(sim)

    # Combined: apply all then add interactions
    combined = dict(baseline)
    for aid in actions:
        eff = ACTION_EFFECTS.get(aid, {})
        for k, dv in eff.items():
            combined[k] = safe_float(combined.get(k, 0), 0) + dv

    interaction_effects = []
    for (a1, a2), inter in INTERACTIONS.items():
        if a1 in actions and a2 in actions:
            for k, dv in inter.items():
                if k == "note":
                    continue
                combined[k] = safe_float(combined.get(k, 0), 0) + dv
            interaction_effects.append({
                "actions": [a1, a2],
                "deltas": {k: v for k, v in inter.items() if k != "note"},
                "note": inter.get("note", ""),
            })

    # Cap into realistic ranges
    combined["vulnerability"] = clamp(combined.get("vulnerability", 50), 0, 100)
    combined["thesis_power"] = clamp(combined.get("thesis_power", 50), 0, 100)
    combined["director_replaceability_avg"] = clamp(combined.get("director_replaceability_avg", 50), 0, 100)
    combined["expected_activist_vote_pct"] = clamp(combined.get("expected_activist_vote_pct", 35), 0, 100)
    combined["p_against_specific_director"] = probability_clamp(combined.get("p_against_specific_director", 0.3))
    combined["board_seat_loss_p"] = probability_clamp(combined.get("board_seat_loss_p", 0.3))
    combined["settlement_pressure_index"] = clamp(combined.get("settlement_pressure_index", 50), 0, 100)

    # Find best single action and best combined package
    def _total_reduction(post, base):
        # Sum of meaningful improvements
        return (
            (base["vulnerability"] - post["vulnerability"]) +
            (base["thesis_power"] - post["thesis_power"]) * 0.5 +
            (base["settlement_pressure_index"] - post["settlement_pressure_index"]) +
            (base["board_seat_loss_p"] - post["board_seat_loss_p"]) * 50
        )

    best_single_action_id = max(action_effects, key=lambda a: _total_reduction(a["post_state"], baseline))["action_id"] if action_effects else None

    # Risk waterfall: baseline -> action-by-action -> interactions -> final
    waterfall = [{"label": "Baseline", "score": round(baseline["vulnerability"], 1), "delta": 0.0}]
    running = baseline["vulnerability"]
    for ae in action_effects:
        d = ae["deltas"].get("vulnerability", 0)
        running += d
        waterfall.append({
            "label": f"After {ae['action_id']}",
            "score": round(clamp(running), 1),
            "delta": round(d, 1),
        })
    for inter in interaction_effects:
        d = inter["deltas"].get("vulnerability", 0)
        running += d
        waterfall.append({
            "label": f"Interaction: {'+'.join(inter['actions'])}",
            "score": round(clamp(running), 1),
            "delta": round(d, 1),
        })
    waterfall.append({"label": "Final (post-package)", "score": round(combined["vulnerability"], 1), "delta": 0.0})

    delta_vs_baseline = {
        "vulnerability": round(combined["vulnerability"] - baseline["vulnerability"], 1),
        "thesis_power": round(combined["thesis_power"] - baseline["thesis_power"], 1),
        "director_replaceability_avg": round(combined["director_replaceability_avg"] - baseline["director_replaceability_avg"], 1),
        "expected_activist_vote_pct": round(combined["expected_activist_vote_pct"] - baseline["expected_activist_vote_pct"], 1),
        "board_seat_loss_p": round(combined["board_seat_loss_p"] - baseline["board_seat_loss_p"], 3),
        "settlement_pressure_index": round(combined["settlement_pressure_index"] - baseline["settlement_pressure_index"], 1),
    }

    summary = (
        f"Causal twin: combined package shifts modeled activism risk and downstream variables. "
        f"Vulnerability {baseline['vulnerability']:.0f} -> {combined['vulnerability']:.0f}; "
        f"settlement pressure {baseline['settlement_pressure_index']:.0f} -> {combined['settlement_pressure_index']:.0f}; "
        f"board seat loss prob {baseline['board_seat_loss_p']:.0%} -> {combined['board_seat_loss_p']:.0%}."
    )

    return {
        "baseline": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in baseline.items()},
        "post_state": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in combined.items()},
        "delta_vs_baseline": delta_vs_baseline,
        "action_effects": action_effects,
        "interaction_effects": interaction_effects,
        "best_single_action": best_single_action_id,
        "best_combined_package": actions,
        "risk_waterfall": waterfall,
        "summary": summary,
    }
