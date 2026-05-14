# Scoring engine + pipeline integration tests. Cheap to run, hits every
# company in the sample dataset since it loads the data once and reuses.
import pytest

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis


@pytest.fixture(scope="module")
def data():
    return load_all_data("data")


@pytest.fixture(scope="module")
def results(data):
    # Run the full pipeline once for each company. Module-scoped so we
    # don't re-pay the ~150ms per-company cost on every test.
    return {
        cid: run_company_analysis(cid, data)
        for cid in data["companies"]["company_id"].astype(str).tolist()
    }


# vulnerability ----------------------------------------------------------

def test_vulnerability_scores_in_range(results):
    for cid, r in results.items():
        s = r["vulnerability"]["score"]
        assert 0 <= s <= 100, f"{cid} vulnerability {s} out of [0,100]"


def test_indc_more_vulnerable_than_nvtc(results):
    # INDC is the stressed industrial, NVTC is the outperformer.
    indc = results["INDC"]["vulnerability"]["score"]
    nvtc = results["NVTC"]["vulnerability"]["score"]
    assert indc > nvtc, f"INDC ({indc}) should be > NVTC ({nvtc})"


def test_vulnerability_has_explanation(results):
    for cid, r in results.items():
        expl = r["vulnerability"].get("explanation")
        assert expl, f"{cid} missing explanation"
        assert isinstance(expl, list)


# fixability -------------------------------------------------------------

def test_fixability_classifies_into_known_labels(results):
    valid = {"Value trap", "Watchlist", "Fixable target",
             "High-conviction fixable target"}
    for cid, r in results.items():
        cls = r["fixability"]["classification"]
        assert cls in valid, f"{cid} bad classification {cls}"


def test_indc_more_fixable_than_mdco(results):
    # INDC is operationally fixable - classified board is a fight,
    # not a moat. MDCO has dual-class + controlled-co structure that
    # blocks the typical activist playbook regardless of operational
    # weakness, so it should rate lower on fixability.
    indc = results["INDC"]["fixability"]["score"]
    mdco = results["MDCO"]["fixability"]["score"]
    assert indc > mdco, (
        f"INDC ({indc}) should be more fixable than MDCO ({mdco})"
    )


# legal feasibility ------------------------------------------------------

def test_mdco_low_legal_feasibility(results):
    mdco = results["MDCO"]["legal"]["legal_feasibility_score"]
    nvtc = results["NVTC"]["legal"]["legal_feasibility_score"]
    assert mdco < nvtc
    assert mdco < 60, f"MDCO legal feasibility should be low, got {mdco}"


def test_compliance_note_present(results):
    # We promised legal we'd surface the "not legal advice" note in the
    # legal calendar output for every company. Don't remove this.
    for cid, r in results.items():
        text = " ".join(str(v) for v in r["legal"].values() if isinstance(v, str))
        assert "legal advice" in text.lower(), (
            f"{cid}: compliance note missing from legal output"
        )


# director scoring -------------------------------------------------------

def test_long_tenure_low_vote_director_ranks_high(results):
    # At least one company in the universe should have a tenured + low-vote
    # director showing up in the top-3 most-replaceable. If this stops firing,
    # the director scoring engine has stopped weighting tenure or vote history.
    found = False
    for cid, r in results.items():
        dirs = r["director_scores"]
        if not dirs:
            continue
        top3 = sorted(dirs, key=lambda d: -float(d["score"]))[:3]
        for d in top3:
            tenure = float(d.get("tenure_years", 0) or 0)
            vote = float(d.get("prior_vote_support_pct", 100) or 100)
            if tenure >= 10 and vote <= 80:
                found = True
                break
        if found:
            break
    assert found, "No long-tenure + low-vote director landed in top 3 anywhere"


def test_director_scores_are_in_range(results):
    for cid, r in results.items():
        for d in r["director_scores"]:
            s = float(d["score"])
            assert 0 <= s <= 100, f"{cid} {d['name']} score {s} out of range"


# pipeline contract ------------------------------------------------------
# The full set of keys every downstream consumer expects on the analysis
# dict. If you're tempted to remove one, check the dashboard first.

REQUIRED_KEYS = [
    "company", "financials", "directors", "shareholders", "ownerships",
    "events", "campaigns", "archetypes", "proxy_advisor_cases",
    "vulnerability", "fixability", "legal", "triggers",
    "activist_dna", "activist_dna_top",
    "theses", "primary_thesis",
    "director_scores", "nominee_profiles", "slate",
    "claim_graph", "claim_attack_table", "claim_defense_table",
    "shareholder_graph", "coalition", "swing_shareholders",
    "proxy_advisor", "defense", "simulation", "settlement",
    "defense_actions", "defense_package",
    "causal_twin", "market_reaction",
    "final_score", "bank_opportunity",
    "board_memo", "war_room",
]


def test_pipeline_returns_all_required_keys(results):
    for cid, r in results.items():
        missing = [k for k in REQUIRED_KEYS if k not in r]
        assert not missing, f"{cid} missing keys: {missing}"


def test_board_memo_non_empty_string(results):
    for cid, r in results.items():
        bm = r["board_memo"]
        assert isinstance(bm, str)
        assert len(bm) > 500, f"{cid} memo too short: {len(bm)} chars"


def test_war_room_has_all_sections(results):
    expected = {"red_team_attack", "blue_team_defense", "board_qa",
                "investor_talking_points", "press_narrative"}
    for cid, r in results.items():
        wr = r["war_room"]
        assert isinstance(wr, dict)
        missing = expected - set(wr.keys())
        assert not missing, f"{cid} war room missing: {missing}"


def test_final_risk_level_valid(results):
    valid = {"Critical", "High", "Moderate", "Low"}
    for cid, r in results.items():
        level = r["final_score"]["final_risk_level"]
        assert level in valid, f"{cid} unknown level: {level}"


def test_primary_thesis_exists(results):
    for cid, r in results.items():
        pt = r["primary_thesis"]
        assert pt
        assert pt.get("name")
        assert "score" in pt
