# Simulation tests: Monte Carlo, counterfactuals, causal twin, settlement,
# market reaction. The MC tests do real sampling (3000 sims) so they're a
# little slower than the scoring tests but still under a second total.
import pytest

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis
from aegis.simulation.proxy_monte_carlo import run_proxy_monte_carlo
from aegis.simulation.counterfactuals import (
    optimize_defense_package, generate_defense_actions,
)


@pytest.fixture(scope="module")
def data():
    return load_all_data("data")


@pytest.fixture(scope="module")
def base_result(data):
    # ORCX is the energy major - a useful middle-of-the-road test case
    # because it has signal on every component but isn't dominated by any
    # single structural feature.
    return run_company_analysis("ORCX", data)


# Monte Carlo ------------------------------------------------------------

def test_mc_probabilities_in_range(base_result):
    sim = base_result["simulation"]
    for k in ("p_private_settlement", "p_public_campaign", "p_proxy_vote",
              "p_activist_wins_1_plus", "p_activist_wins_2_plus",
              "p_activist_wins_3_plus", "p_company_full_defense",
              "p_strategic_review"):
        v = float(sim[k])
        assert 0.0 <= v <= 1.0, f"{k}={v} out of [0,1]"


def test_mc_more_coalition_means_more_wins(base_result):
    # Holding everything else fixed, lift the activist coalition by ~25pp
    # and the win probability should obviously go up. If this fails, the
    # MC is no longer reading the coalition input correctly.
    common = dict(
        director_scores=base_result["director_scores"],
        pa_view=base_result["proxy_advisor"],
        defense_result=base_result["defense"],
        settlement_pressure=50,
        n_simulations=3000,
        random_seed=42,
        _run_sensitivity=False,
    )
    low  = run_proxy_monte_carlo(coalition={"expected_activist_vote_pct": 30.0}, **common)
    high = run_proxy_monte_carlo(coalition={"expected_activist_vote_pct": 55.0}, **common)
    assert high["p_activist_wins_1_plus"] > low["p_activist_wins_1_plus"], (
        f"raised coalition did not raise wins: "
        f"low={low['p_activist_wins_1_plus']} high={high['p_activist_wins_1_plus']}"
    )


def test_mc_stronger_defense_lowers_activist_win(base_result):
    common = dict(
        coalition=base_result["coalition"],
        director_scores=base_result["director_scores"],
        pa_view=base_result["proxy_advisor"],
        settlement_pressure=50,
        n_simulations=3000,
        random_seed=42,
        _run_sensitivity=False,
    )
    weak   = run_proxy_monte_carlo(defense_result={"defense_strength_score": 35}, **common)
    strong = run_proxy_monte_carlo(defense_result={"defense_strength_score": 80}, **common)
    assert strong["p_activist_wins_1_plus"] < weak["p_activist_wins_1_plus"]


def test_mc_n_simulations_zero_does_not_crash(base_result):
    # Regression test for a crash where run_proxy_monte_carlo(n_simulations=0)
    # raised ZeroDivisionError. Edge case that came up during fuzz testing.
    out = run_proxy_monte_carlo(
        coalition=base_result["coalition"],
        director_scores=base_result["director_scores"],
        pa_view=base_result["proxy_advisor"],
        defense_result=base_result["defense"],
        settlement_pressure=50,
        n_simulations=0,
        random_seed=42,
        _run_sensitivity=False,
    )
    assert out["n_simulations"] == 0
    assert out["p_activist_wins_1_plus"] == 0.0


def test_mc_deterministic_with_same_seed(base_result):
    # Same seed -> same numbers. If this breaks, someone introduced an
    # ungated source of randomness somewhere in the call graph.
    kw = dict(
        coalition=base_result["coalition"],
        director_scores=base_result["director_scores"],
        pa_view=base_result["proxy_advisor"],
        defense_result=base_result["defense"],
        settlement_pressure=50,
        n_simulations=2000,
        random_seed=42,
        _run_sensitivity=False,
    )
    a = run_proxy_monte_carlo(**kw)
    b = run_proxy_monte_carlo(**kw)
    assert a["p_activist_wins_1_plus"] == b["p_activist_wins_1_plus"]
    assert a["p_activist_wins_2_plus"] == b["p_activist_wins_2_plus"]
    assert a["p_proxy_vote"] == b["p_proxy_vote"]


def test_mc_scenario_counts_sum_to_n_sims(base_result):
    # Regression test for a real bug from May 2026: the catch-all `else`
    # in the MC scenario classifier incremented two counters per sim,
    # which inflated scenario_counts totals up to 1.5x n_simulations and
    # double-inflated p_public_campaign. Every sim must increment exactly
    # one bucket so the totals reconcile.
    sim = base_result["simulation"]
    counts = sim.get("scenario_counts") or {}
    total = sum(v for v in counts.values() if isinstance(v, (int, float)))
    n_sims = sim.get("n_simulations")
    assert total == n_sims, (
        f"scenario_counts sum {total} != n_simulations {n_sims}; "
        f"some simulations are being counted in multiple buckets"
    )


def test_mc_probabilities_partition_correctly(base_result):
    # The three top-level scenario probabilities (settle / vote / strategic
    # review) should partition the sample space: their sum should be very
    # close to 1.0.
    sim = base_result["simulation"]
    p_settle = float(sim.get("p_private_settlement", 0))
    p_vote = float(sim.get("p_proxy_vote", 0))
    p_review = float(sim.get("p_strategic_review", 0))
    total = p_settle + p_vote + p_review
    assert 0.97 <= total <= 1.03, (
        f"settle + vote + review = {total:.3f}, expected ~1.0"
    )


# settlement -------------------------------------------------------------

def test_settlement_returns_valid_best_option(base_result):
    s = base_result["settlement"]
    best = s.get("best_option") or {}
    assert best
    assert "option_name" in best
    assert "utility_score" in best
    assert 0 <= float(best["utility_score"]) <= 100


def test_settlement_recommended_path_present(base_result):
    rp = base_result["settlement"]["recommended_path"]
    assert isinstance(rp, str) and rp


# counterfactual defense package -----------------------------------------

def test_defense_package_reduces_risk():
    # Stand-alone test - we don't need the full pipeline output here.
    pkg = optimize_defense_package(
        actions=generate_defense_actions(),
        vulnerability={"score": 70},
        initial_risk_score=70.0,
        max_actions=5,
    )
    assert pkg["estimated_risk_reduction"] >= 0
    assert pkg["estimated_risk_after"] <= pkg["estimated_risk_before"]


# causal twin ------------------------------------------------------------

def test_causal_twin_returns_deltas(base_result):
    ct = base_result["causal_twin"]
    assert "delta_vs_baseline" in ct
    assert isinstance(ct["delta_vs_baseline"], dict)
    assert "baseline" in ct and "post_state" in ct


# market reaction --------------------------------------------------------

def test_market_reaction_scenarios_present(base_result):
    mr = base_result["market_reaction"]
    assert "scenario_reactions" in mr
    assert "expected_reaction_weighted_pp" in mr
