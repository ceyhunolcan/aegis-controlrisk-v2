# End-to-end smoke check. Loads the synthetic dataset, runs the pipeline
# for every company, and verifies the analysis dict has all required keys,
# scores in [0,100], probabilities in [0,1], a non-empty memo, all war
# room sections, plus a determinism check (same seed -> same numbers).
#
# Exits nonzero on any failure. Designed to run in under 2 seconds so it's
# cheap to fire pre-commit.
import sys
import time
import traceback

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis


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

# (key on result dict, sub-key, expected range)
SCORE_CHECKS = [
    ("vulnerability",     "score",                          (0, 100)),
    ("fixability",        "score",                          (0, 100)),
    ("defense",           "defense_strength_score",         (0, 100)),
    ("bank_opportunity",  "mandate_opportunity_score",      (0, 100)),
    ("final_score",       "activism_risk_score_0_100",      (0, 100)),
    ("triggers",          "trigger_score",                  (0, 100)),
]

PROB_CHECKS = [
    ("simulation", "p_private_settlement"),
    ("simulation", "p_proxy_vote"),
    ("simulation", "p_activist_wins_1_plus"),
    ("simulation", "p_activist_wins_2_plus"),
    ("simulation", "p_activist_wins_3_plus"),
    ("simulation", "p_company_full_defense"),
    ("simulation", "p_strategic_review"),
    ("final_score", "activism_event_probability_12m"),
    ("final_score", "control_loss_probability_if_attacked"),
    ("final_score", "board_seat_loss_probability"),
    ("proxy_advisor", "p_support_management_full_slate"),
    ("proxy_advisor", "p_support_one_activist_nominee"),
    ("proxy_advisor", "p_support_two_plus_activist_nominees"),
    ("proxy_advisor", "p_recommend_against_pay"),
]

WAR_ROOM_SECTIONS = ("red_team_attack", "blue_team_defense", "board_qa",
                     "investor_talking_points", "press_narrative")


def _range_check(result, top, sub, lo, hi, errs):
    val = (result.get(top) or {}).get(sub)
    try:
        v = float(val)
    except (TypeError, ValueError):
        errs.append(f"{top}.{sub}: non-numeric {val!r}")
        return
    if not (lo <= v <= hi):
        errs.append(f"{top}.{sub}: {v} out of [{lo},{hi}]")


def _check_company(result):
    errs = []

    missing = [k for k in REQUIRED_KEYS if k not in result]
    if missing:
        errs.append(f"missing keys: {missing}")

    for top, sub, (lo, hi) in SCORE_CHECKS:
        _range_check(result, top, sub, lo, hi, errs)
    for top, sub in PROB_CHECKS:
        _range_check(result, top, sub, 0.0, 1.0, errs)

    bm = result.get("board_memo", "")
    if not isinstance(bm, str):
        errs.append("board_memo: not a string")
    elif len(bm) < 500:
        errs.append(f"board_memo: too short ({len(bm)} chars)")

    wr = result.get("war_room", {})
    if not isinstance(wr, dict):
        errs.append("war_room: not a dict")
    else:
        for section in WAR_ROOM_SECTIONS:
            if section not in wr:
                errs.append(f"war_room missing section: {section}")

    if not result.get("director_scores"):
        errs.append("director_scores empty")
    if not result.get("theses"):
        errs.append("theses empty")
    return errs


def run_smoke_test():
    print("=== Aegis ControlRisk OS v2 — Smoke Test ===\n")
    t0 = time.time()

    print("[1/3] Loading synthetic data...")
    try:
        data = load_all_data("data")
    except Exception as e:
        print(f"  FAIL: could not load data: {e}")
        traceback.print_exc()
        return 1
    companies_df = data["companies"]
    n = len(companies_df)
    print(f"  Loaded {n} companies, {len(data['directors'])} directors, "
          f"{len(data['shareholders'])} shareholders, "
          f"{len(data['ownership'])} ownership rows, "
          f"{len(data['campaigns'])} historical campaigns.\n")

    print(f"[2/3] Running pipeline for all {n} companies...")
    failures = []
    for cid in companies_df["company_id"].astype(str).tolist():
        print(f"  - {cid}...", end=" ", flush=True)
        t1 = time.time()
        try:
            result = run_company_analysis(cid, data)
        except Exception as e:
            print(f"CRASH: {e}")
            traceback.print_exc()
            failures.append((cid, [f"crash: {e}"]))
            continue
        elapsed = time.time() - t1

        errs = _check_company(result)
        if errs:
            failures.append((cid, errs))
            print(f"FAIL ({elapsed:.1f}s)")
            for err in errs:
                print(f"      {err}")
        else:
            bm_len = len(result.get("board_memo", ""))
            level = (result.get("final_score") or {}).get("final_risk_level", "—")
            print(f"OK ({elapsed:.1f}s, memo={bm_len} chars, risk={level})")

    print("\n[3/3] Determinism check: re-running ORCX with same seed...")
    try:
        r1 = run_company_analysis("ORCX", data)
        r2 = run_company_analysis("ORCX", data)
        p1 = r1["simulation"]["p_activist_wins_1_plus"]
        p2 = r2["simulation"]["p_activist_wins_1_plus"]
        if abs(p1 - p2) < 1e-9:
            print(f"  OK (p_activist_wins_1_plus = {p1} both runs)")
        else:
            print(f"  FAIL: {p1} vs {p2}")
            failures.append(("ORCX_determinism",
                             [f"diff p_activist_wins_1_plus: {p1} vs {p2}"]))
    except Exception as e:
        print(f"  FAIL: {e}")
        failures.append(("determinism", [str(e)]))

    elapsed = time.time() - t0
    print(f"\n=== Smoke test complete in {elapsed:.1f}s ===")
    print(f"   Companies passed: {n - len(failures)}/{n}")
    if failures:
        print("   FAILURES:")
        for cid, errs in failures:
            print(f"     {cid}: {errs}")
        return 1
    print("   All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run_smoke_test())
