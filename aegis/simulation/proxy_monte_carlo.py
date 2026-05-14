# Proxy contest Monte Carlo. Given a coalition + PA stance + defense strength,
# sample N=10000 votes and roll up the distribution of outcomes (settlement /
# vote / strategic review). Seeded - same inputs always produce same probs.
#
# The sensitivity dict at the end re-runs the MC with small one-variable flexes
# so you can show "what happens if PA flips" without rebuilding the call site.
# The _run_sensitivity flag is there because the sub-call would otherwise
# recurse forever, ask me how I know.
import numpy as np

from ..utils.normalization import clamp, safe_float, safe_get, probability_clamp
from config import DEFAULT_N_SIMULATIONS, RANDOM_SEED


def _outcome_label(activist_pct, mgmt_pct, slate_size=3):
    """Map a vote outcome to discrete seats won + scenario bucket."""
    # Heuristic: if activist coalition > 50%, activist wins all slate seats;
    # if 45-50%, wins partial; if <45%, mgmt full defense
    if activist_pct >= 55:
        seats = slate_size
        scenario = "proxy_vote_activist_full"
    elif activist_pct >= 50:
        seats = max(slate_size - 1, 1)
        scenario = "proxy_vote_activist_partial"
    elif activist_pct >= 45:
        seats = 1
        scenario = "proxy_vote_split"
    elif activist_pct >= 40:
        # Likely settles for 1 seat to avoid going to vote
        seats = 1
        scenario = "settlement_1_seat"
    elif activist_pct >= 35:
        # Often a settlement at this band
        seats = 0  # governance reforms only, no board seat
        scenario = "settlement_governance_only"
    else:
        seats = 0
        scenario = "company_full_defense"
    return {"seats_won": seats, "scenario": scenario}


def _sample_pa_endorsement(p_one, p_two, rng):
    """Sample how many activist nominees PA endorses (0/1/2)."""
    r = rng.random()
    if r < p_two:
        return 2
    if r < p_one:
        return 1
    return 0


def _coalition_with_noise(
    coalition, defense_strength, pa_endorse, rng):
    """Sample an activist coalition pct for a single simulation."""
    base_a = safe_float(coalition.get("expected_activist_vote_pct", 35), 35)

    # Defense reduces activist vote share by up to ~10 pp at full strength
    defense_shift = (defense_strength - 50) / 100.0 * 12.0
    base_a -= defense_shift

    # PA endorsement effect: each endorsed nominee shifts ~8pp
    base_a += pa_endorse * 7.0

    # Noise: turnout, last-minute swings
    noise = rng.normal(0, 4.5)
    sampled = base_a + noise
    return clamp(sampled, 0, 100)


def run_proxy_monte_carlo(
    coalition,
    director_scores,
    pa_view,
    defense_result,
    settlement_pressure = None,
    n_simulations = DEFAULT_N_SIMULATIONS,
    random_seed = RANDOM_SEED,
    slate_size = 3,
    _run_sensitivity = True):
    """Run Monte Carlo simulation of activist outcomes."""
    rng = np.random.default_rng(int(random_seed))

    # Safe defaults
    if not coalition:
        coalition = {"expected_activist_vote_pct": 30.0}
    if not director_scores:
        # Neutral 50 baseline
        director_scores = [{"score": 50.0}]
    if not pa_view:
        pa_view = {"p_support_one_activist_nominee": 0.3, "p_support_two_plus_activist_nominees": 0.10}
    if not defense_result:
        defense_result = {"defense_strength_score": 50}

    p_one = safe_float(pa_view.get("p_support_one_activist_nominee", 0.3), 0.3)
    p_two = safe_float(pa_view.get("p_support_two_plus_activist_nominees", 0.10), 0.10)
    # Ensure p_two <= p_one for sampling
    if p_two > p_one:
        p_two = p_one * 0.6

    defense_strength = safe_float(defense_result.get("defense_strength_score", 50), 50)

    # Pre-settlement effect: probability mgmt offers settlement before vote
    if settlement_pressure is None:
        settlement_pressure = 50.0
    p_settle_pre_vote = clamp(settlement_pressure / 200.0 + 0.10, 0.05, 0.65)

    # Counters. Every simulation increments exactly ONE of these so that
    # sum(counts.values()) == n_simulations. Used to be a subtle bug here
    # where the catch-all `else` branch incremented both company_full_defense
    # AND proxy_vote_company_wins, inflating the scenario_counts total and
    # p_public_campaign.
    counts = {
        "private_settlement": 0,
        "proxy_vote_company_wins": 0,    # also called "company full defense"
        "proxy_vote_split": 0,           # activist gets 1 seat in vote
        "proxy_vote_activist_partial": 0,
        "proxy_vote_activist_full": 0,
        "strategic_review": 0,
        "settlement_governance_only": 0,
        "settlement_1_seat": 0,
    }
    seats_won = []
    activist_vote_samples = []

    for _ in range(int(n_simulations)):
        # Pre-vote settlement path
        if rng.random() < p_settle_pre_vote:
            # private settlement
            # Settlement may or may not include a strategic review
            if rng.random() < 0.20:
                counts["strategic_review"] += 1
                seats_won.append(2)
                activist_vote_samples.append(50.0)
            else:
                counts["private_settlement"] += 1
                seats_won.append(rng.integers(0, 3))  # 0, 1, or 2
                activist_vote_samples.append(45.0)
            continue

        # PA endorsement
        pa_e = _sample_pa_endorsement(p_one, p_two, rng)
        # Sample coalition outcome
        activist_pct = _coalition_with_noise(coalition, defense_strength, pa_e, rng)
        activist_vote_samples.append(activist_pct)

        outcome = _outcome_label(activist_pct, 100 - activist_pct, slate_size)
        scen = outcome["scenario"]

        # Each sim goes into exactly one bucket. The _outcome_label() call
        # returns one of six scenario names; map "company_full_defense" to
        # proxy_vote_company_wins so the count names match the
        # p_public_campaign sum below.
        if scen == "proxy_vote_activist_full":
            counts["proxy_vote_activist_full"] += 1
        elif scen == "proxy_vote_activist_partial":
            counts["proxy_vote_activist_partial"] += 1
        elif scen == "proxy_vote_split":
            counts["proxy_vote_split"] += 1
        elif scen == "settlement_1_seat":
            counts["settlement_1_seat"] += 1
        elif scen == "settlement_governance_only":
            counts["settlement_governance_only"] += 1
        else:  # company_full_defense
            counts["proxy_vote_company_wins"] += 1

        seats_won.append(outcome["seats_won"])

    # Guard against n_simulations=0 — divide-by-zero would otherwise blow
    # up here, and seats_array.mean() throws on empty arrays. Return zeros.
    n = float(n_simulations)
    if n <= 0:
        return {
            "n_simulations": 0,
            "random_seed": int(random_seed),
            "p_private_settlement": 0.0,
            "p_public_campaign": 0.0,
            "p_proxy_vote": 0.0,
            "p_activist_wins_1_plus": 0.0,
            "p_activist_wins_2_plus": 0.0,
            "p_activist_wins_3_plus": 0.0,
            "p_company_full_defense": 0.0,
            "p_strategic_review": 0.0,
            "scenario_counts": counts,
            "expected_seats_won": 0.0,
            "p25_activist_vote_pct": 0.0,
            "median_activist_vote_pct": 0.0,
            "p75_activist_vote_pct": 0.0,
            "sensitivity": {},
            "interpretation": "n_simulations=0; nothing simulated.",
        }

    p_private_settlement = (
        counts["private_settlement"]
        + counts["settlement_1_seat"]
        + counts["settlement_governance_only"]
    ) / n
    p_strategic_review = counts["strategic_review"] / n
    p_public_campaign = (
        counts["proxy_vote_activist_full"]
        + counts["proxy_vote_activist_partial"]
        + counts["proxy_vote_split"]
        + counts["proxy_vote_company_wins"]
    ) / n
    p_proxy_vote = p_public_campaign  # treat as same
    p_company_full_defense = counts["proxy_vote_company_wins"] / n

    seats_array = np.array(seats_won) if seats_won else np.array([0])
    p_wins_1_plus = float((seats_array >= 1).mean())
    p_wins_2_plus = float((seats_array >= 2).mean())
    p_wins_3_plus = float((seats_array >= 3).mean())

    # Sensitivity: 5 scenario flexes (skipped in sub-calls)
    if _run_sensitivity:
        sens = _sensitivity(coalition, director_scores, pa_view, defense_result,
                             settlement_pressure, random_seed, slate_size)
    else:
        sens = {}

    interp = (
        f"Across {int(n)} simulations: "
        f"P(private settlement)={p_private_settlement:.0%}, "
        f"P(proxy vote)={p_proxy_vote:.0%}, "
        f"P(activist wins ≥1 seat)={p_wins_1_plus:.0%}, "
        f"P(activist wins ≥2 seats)={p_wins_2_plus:.0%}."
    )

    return {
        "n_simulations": int(n_simulations),
        "random_seed": int(random_seed),
        "p_private_settlement": round(probability_clamp(p_private_settlement), 3),
        "p_public_campaign": round(probability_clamp(p_public_campaign), 3),
        "p_proxy_vote": round(probability_clamp(p_proxy_vote), 3),
        "p_activist_wins_1_plus": round(probability_clamp(p_wins_1_plus), 3),
        "p_activist_wins_2_plus": round(probability_clamp(p_wins_2_plus), 3),
        "p_activist_wins_3_plus": round(probability_clamp(p_wins_3_plus), 3),
        "p_company_full_defense": round(probability_clamp(p_company_full_defense), 3),
        "p_strategic_review": round(probability_clamp(p_strategic_review), 3),
        "scenario_counts": counts,
        "expected_seats_won": round(float(seats_array.mean()), 2),
        "p25_activist_vote_pct": round(float(np.percentile(activist_vote_samples, 25)), 1),
        "median_activist_vote_pct": round(float(np.median(activist_vote_samples)), 1),
        "p75_activist_vote_pct": round(float(np.percentile(activist_vote_samples, 75)), 1),
        "sensitivity": sens,
        "interpretation": interp,
    }


def _sensitivity(coalition, director_scores, pa_view, defense_result,
                 settlement_pressure, random_seed, slate_size):
    """Run 5 flexes of one input each, holding others fixed."""
    flexes = {}

    def _run(c, p, d, label):
        out = run_proxy_monte_carlo(
            c, director_scores, p, d, settlement_pressure,
            n_simulations=2000, random_seed=random_seed, slate_size=slate_size,
            _run_sensitivity=False,
        )
        flexes[label] = {
            "p_activist_wins_1_plus": out["p_activist_wins_1_plus"],
            "p_activist_wins_2_plus": out["p_activist_wins_2_plus"],
            "p_company_full_defense": out["p_company_full_defense"],
        }

    # 1. +5pp shareholder coalition
    c_high = dict(coalition or {})
    c_high["expected_activist_vote_pct"] = safe_float(c_high.get("expected_activist_vote_pct", 35), 35) + 5
    _run(c_high, pa_view, defense_result, "coalition_+5pp")

    # 2. -5pp shareholder coalition
    c_low = dict(coalition or {})
    c_low["expected_activist_vote_pct"] = safe_float(c_low.get("expected_activist_vote_pct", 35), 35) - 5
    _run(c_low, pa_view, defense_result, "coalition_-5pp")

    # 3. PA endorses activist (+0.20 on p_one)
    pa_high = dict(pa_view or {})
    pa_high["p_support_one_activist_nominee"] = clamp(safe_float(pa_high.get("p_support_one_activist_nominee", 0.3), 0.3) + 0.20, 0, 1)
    pa_high["p_support_two_plus_activist_nominees"] = clamp(safe_float(pa_high.get("p_support_two_plus_activist_nominees", 0.1), 0.1) + 0.10, 0, 1)
    _run(coalition, pa_high, defense_result, "pa_endorse_activist")

    # 4. PA backs management (-0.20)
    pa_low = dict(pa_view or {})
    pa_low["p_support_one_activist_nominee"] = clamp(safe_float(pa_low.get("p_support_one_activist_nominee", 0.3), 0.3) - 0.20, 0, 1)
    pa_low["p_support_two_plus_activist_nominees"] = clamp(safe_float(pa_low.get("p_support_two_plus_activist_nominees", 0.1), 0.1) - 0.10, 0, 1)
    _run(coalition, pa_low, defense_result, "pa_back_management")

    # 5. Defense improves +15 points
    d_high = dict(defense_result or {})
    d_high["defense_strength_score"] = clamp(safe_float(d_high.get("defense_strength_score", 50), 50) + 15, 0, 100)
    _run(coalition, pa_view, d_high, "defense_+15")

    return flexes
