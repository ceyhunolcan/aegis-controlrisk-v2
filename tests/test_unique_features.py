# Smoke tests for the bits that differentiate CASCADE-2 from a generic
# risk scorer: activist DNA, claim graph, nominee matchup, swing
# shareholders, PA shadow, causal twin, bank opportunity, and the memo +
# war room generators. INDC (the deliberately-stressed industrial) is a
# good universal test fixture because every engine has something to say
# about it.
import pytest

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis


@pytest.fixture(scope="module")
def data():
    return load_all_data("data")


@pytest.fixture(scope="module")
def result(data):
    return run_company_analysis("INDC", data)


# activist DNA -----------------------------------------------------------

def test_activist_dna_ranks_at_least_one(result):
    dna = result["activist_dna"]
    assert isinstance(dna, list) and len(dna) >= 1
    top = result["activist_dna_top"]
    assert top
    assert "name" in top
    assert "fit_score" in top
    assert 0 <= float(top["fit_score"]) <= 100


def test_activist_dna_has_campaign_style_and_stake(result):
    top = result["activist_dna_top"]
    assert top.get("likely_campaign_style")
    assert "likely_stake_pct" in top
    assert "likely_board_seats_requested" in top


# claim graph ------------------------------------------------------------

def test_claim_graph_returns_claims(result):
    cg = result["claim_graph"]
    assert isinstance(cg, dict)
    assert "graph" in cg and "claims" in cg
    assert len(cg["claims"]) >= 1
    c0 = cg["claims"][0]
    # Tolerate either 'claim_text' or legacy 'claim' field name
    assert c0.get("claim_text") or c0.get("claim"), f"no claim text: {c0}"
    for field in ("evidence_strength", "rebuttability",
                  "claim_power_score", "shareholder_resonance"):
        assert field in c0, f"claim missing {field}"


def test_attack_and_defense_tables_present(result):
    att = result["claim_attack_table"]
    deftab = result["claim_defense_table"]
    assert isinstance(att, list) and len(att) >= 1
    assert isinstance(deftab, list) and len(deftab) >= 1


# nominee matchup --------------------------------------------------------

def test_nominee_profiles_present(result):
    nominees = result["nominee_profiles"]
    assert isinstance(nominees, list) and len(nominees) >= 1
    for n in nominees[:3]:
        assert (n.get("profile_name") or n.get("profile_type") or n.get("name")), (
            f"nominee missing a label: {n}"
        )


def test_slate_optimization_produces_recommended_slate(result):
    slate = result["slate"]
    assert isinstance(slate, dict)
    rec = slate.get("recommended_slate") or slate.get("slate")
    assert rec, "no recommended slate"
    assert len(rec) >= 1


# swing shareholders -----------------------------------------------------

def test_swing_engine_ranks_holders(result):
    sw = result["swing_shareholders"]
    assert "top_5_priority_outreach" in sw
    top5 = sw["top_5_priority_outreach"]
    assert isinstance(top5, list)
    if top5:
        first = top5[0]
        assert "holder_name" in first or "shareholder_name" in first
        assert "swing_value_score" in first


# proxy advisor shadow ---------------------------------------------------

def test_proxy_advisor_probs_valid(result):
    pa = result["proxy_advisor"]
    for k in ("p_support_management_full_slate",
              "p_support_one_activist_nominee",
              "p_support_two_plus_activist_nominees",
              "p_recommend_against_pay"):
        v = float(pa[k])
        assert 0.0 <= v <= 1.0, f"{k} out of range: {v}"
    assert pa.get("key_drivers"), "PA result missing key_drivers"


# causal twin ------------------------------------------------------------

def test_causal_twin_returns_deltas(result):
    ct = result["causal_twin"]
    assert "delta_vs_baseline" in ct
    assert isinstance(ct["delta_vs_baseline"], dict)
    assert "best_single_action" in ct


# bank opportunity -------------------------------------------------------

def test_bank_opportunity_score_in_range(result):
    bo = result["bank_opportunity"]
    s = float(bo["mandate_opportunity_score"])
    assert 0 <= s <= 100
    assert bo.get("opportunity_level")
    assert bo.get("likely_advisory_products")
    assert bo.get("banker_pitch_angle")


# memo + war room --------------------------------------------------------

def test_board_memo_is_non_empty_string(result):
    bm = result["board_memo"]
    assert isinstance(bm, str)
    assert len(bm) > 1000, f"memo too short: {len(bm)}"
    assert "#" in bm  # markdown
    assert "legal advice" in bm.lower()  # compliance footer


def test_war_room_has_all_sections(result):
    wr = result["war_room"]
    assert isinstance(wr, dict)
    for k in ("red_team_attack", "blue_team_defense", "board_qa",
              "investor_talking_points", "press_narrative"):
        assert k in wr, f"war room missing {k}"
    qa = wr["board_qa"]
    assert isinstance(qa, list) and len(qa) >= 5
    for entry in qa[:3]:
        assert "q" in entry and "a" in entry
