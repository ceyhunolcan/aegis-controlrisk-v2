# Deeper regression harness. The smoke test catches "did it crash and are
# the outputs roughly the right shape." This one looks for the subtle stuff:
# NaN leaks, level/score inconsistency, score monotonicity breaks, output
# quality regressions in the memo (raw Python reprs, runaway em-dashes,
# missing compliance note), settlement-game ordering bugs, hidden error
# strings buried in deep dicts, etc.
#
# Three statuses: PASS / WARN / FAIL. WARN is "weird, but not blocking".
import math
import json
import time
import sys
import re
from collections import Counter, defaultdict

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis


PASS = "\033[32mPASS\033[0m"
WARN = "\033[33mWARN\033[0m"
FAIL = "\033[31mFAIL\033[0m"

log = []


def report(name, status, msg=""):
    log.append((name, status, msg))
    line = f"  {status} {name}"
    if msg:
        line += f" — {msg}"
    print(line)


# Walk every numeric leaf in a nested dict/list. Used to scan for NaN/Inf.
def walk_numbers(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_numbers(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, obj


# Recursively find any key called "error" that has a truthy value.
def find_error_keys(obj, path="", out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "error" and v:
                out.append(f"{path}.error: {str(v)[:80]}")
            find_error_keys(v, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            find_error_keys(x, f"{path}[{i}]", out)
    return out


# ----- setup ----------------------------------------------------------------
print("\n=== Aegis bug test ===\n")
print("Loading data and running pipeline for all companies...")
data = load_all_data("data")
companies = data["companies"]["company_id"].astype(str).tolist()
n = len(companies)

all_results = {}
timings = {}
for cid in companies:
    t0 = time.time()
    try:
        all_results[cid] = run_company_analysis(cid, data)
    except Exception as e:
        all_results[cid] = {"_error": str(e)}
    timings[cid] = time.time() - t0
print(f"Loaded {n} companies, all pipeline runs complete.\n")


# ----- Group 1: bad input robustness ---------------------------------------
print("[Group 1] Pipeline robustness on bad inputs")

# unknown id
try:
    r = run_company_analysis("FAKE_DOES_NOT_EXIST", data)
    if isinstance(r, dict) and "final_score" in r:
        report("unknown_company_id graceful", PASS, "returned safe-default dict")
    else:
        report("unknown_company_id graceful", FAIL, f"got: {type(r)}")
except Exception as e:
    msg = str(e).lower()
    if "not found" in msg or "unknown" in msg or "no such" in msg:
        report("unknown_company_id graceful", PASS, f"raised cleanly: {e}")
    else:
        report("unknown_company_id graceful", WARN,
               f"raised opaque: {type(e).__name__}: {e}")

# empty string id
try:
    r = run_company_analysis("", data)
    report("empty_company_id graceful", PASS if isinstance(r, dict) else FAIL)
except Exception as e:
    report("empty_company_id graceful", WARN, f"raised: {type(e).__name__}")

# None id - should raise, not silently succeed
try:
    r = run_company_analysis(None, data)
    report("none_company_id graceful", WARN, "did not raise (might mask bugs)")
except Exception as e:
    report("none_company_id graceful", PASS, f"raised cleanly: {type(e).__name__}")


# ----- Group 2: numerical sanity -------------------------------------------
print("\n[Group 2] Numerical sanity (NaN / Inf / out-of-range)")

nan_paths, inf_paths = [], []
for cid, r in all_results.items():
    for path, v in walk_numbers(r):
        if isinstance(v, float):
            if math.isnan(v):
                nan_paths.append(f"{cid}{path}={v}")
            elif math.isinf(v):
                inf_paths.append(f"{cid}{path}={v}")

report("no_NaN_in_outputs",
       FAIL if nan_paths else PASS,
       f"{len(nan_paths)} NaN values, e.g. {nan_paths[:3]}" if nan_paths
       else f"checked many leaves across {n} companies")
report("no_Inf_in_outputs",
       FAIL if inf_paths else PASS,
       f"{len(inf_paths)} Inf values, e.g. {inf_paths[:3]}" if inf_paths else "")

# 0-100 score bounds
PCT_FIELDS = [
    ("vulnerability",     "score"),
    ("fixability",        "score"),
    ("defense",           "defense_strength_score"),
    ("bank_opportunity",  "mandate_opportunity_score"),
    ("triggers",          "trigger_score"),
    ("final_score",       "activism_risk_score_0_100"),
    ("final_score",       "settlement_pressure_index"),
    ("legal",             "legal_feasibility_score"),
    ("legal",             "urgency_score"),
    ("proxy_advisor",     "pa_governance_concern_score"),
]
score_violations = []
for cid, r in all_results.items():
    for top, sub in PCT_FIELDS:
        try:
            v = float(r[top][sub])
            if not (0 <= v <= 100):
                score_violations.append(f"{cid}.{top}.{sub}={v}")
        except Exception:
            pass
report("scores_in_0_100",
       FAIL if score_violations else PASS,
       str(score_violations) if score_violations
       else f"all {len(PCT_FIELDS)} score fields × {n} companies in range")

# 0-1 probability bounds
PROB_FIELDS = [
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
prob_violations = []
for cid, r in all_results.items():
    for top, sub in PROB_FIELDS:
        try:
            v = float(r[top][sub])
            if not (0 <= v <= 1):
                prob_violations.append(f"{cid}.{top}.{sub}={v}")
        except Exception:
            pass
report("probs_in_0_1",
       FAIL if prob_violations else PASS,
       str(prob_violations) if prob_violations
       else f"all {len(PROB_FIELDS)} probability fields × {n} companies in range")


# ----- Group 3: monotonicity ------------------------------------------------
print("\n[Group 3] Probability monotonicity (≥3 ≤ ≥2 ≤ ≥1)")

mono_fail = []
for cid, r in all_results.items():
    p1 = r["simulation"]["p_activist_wins_1_plus"]
    p2 = r["simulation"]["p_activist_wins_2_plus"]
    p3 = r["simulation"]["p_activist_wins_3_plus"]
    if not (p1 >= p2 >= p3):
        mono_fail.append(f"{cid}: p1={p1}, p2={p2}, p3={p3}")
report("seats_won_monotone",
       FAIL if mono_fail else PASS,
       "; ".join(mono_fail) if mono_fail
       else "p(≥1) ≥ p(≥2) ≥ p(≥3) for all companies")


# Scenario counts must sum to exactly n_simulations.
# Regression check for a bug where the `else` branch in the MC counter
# double-incremented and inflated the totals.
count_fail = []
for cid, r in all_results.items():
    sim = r.get("simulation") or {}
    counts = sim.get("scenario_counts") or {}
    total = sum(v for v in counts.values() if isinstance(v, (int, float)))
    n_sims = sim.get("n_simulations") or 0
    if total != n_sims:
        count_fail.append(f"{cid}: sum={total}, n_sims={n_sims}")
report("mc_scenario_counts_sum_to_n_sims",
       FAIL if count_fail else PASS,
       "; ".join(count_fail) if count_fail
       else f"scenario_counts sum == n_simulations across {n} companies")


# settle + vote + strategic_review should partition the sample space.
partition_fail = []
for cid, r in all_results.items():
    sim = r.get("simulation") or {}
    p_settle = float(sim.get("p_private_settlement", 0) or 0)
    p_vote = float(sim.get("p_proxy_vote", 0) or 0)
    p_review = float(sim.get("p_strategic_review", 0) or 0)
    s = p_settle + p_vote + p_review
    if not (0.97 <= s <= 1.03):
        partition_fail.append(f"{cid}: sum={s:.3f}")
report("mc_outcome_partition",
       FAIL if partition_fail else PASS,
       "; ".join(partition_fail) if partition_fail
       else f"p(settle) + p(vote) + p(review) ≈ 1.0 across {n} companies")


# ----- Group 4: cross-company invariants -----------------------------------
print("\n[Group 4] Cross-company invariants")

# risk_level should match composite score thresholds, with documented
# escalation rule when both event-prob and control-loss-prob are high
risk_fail = []
for cid, r in all_results.items():
    score = float(r["final_score"]["activism_risk_score_0_100"])
    level = r["final_score"]["final_risk_level"]
    a_p = float(r["final_score"]["activism_event_probability_12m"])
    cl_p = float(r["final_score"]["control_loss_probability_if_attacked"])
    if score >= 80:
        expected = "Critical"
    elif score >= 65:
        expected = "High"
    elif score >= 45:
        expected = "Moderate"
    else:
        expected = "Low"
    # escalation rule
    if a_p >= 0.70 and cl_p >= 0.50:
        if expected == "High":
            expected = "Critical"
        elif expected == "Moderate":
            expected = "High"
    if level != expected:
        risk_fail.append(
            f"{cid}: score={score}, level={level}, expected={expected} "
            f"(p_event={a_p:.2f}, p_control_loss={cl_p:.2f})"
        )
report("risk_level_matches_score",
       FAIL if risk_fail else PASS,
       "; ".join(risk_fail) if risk_fail
       else "all companies consistent with thresholds + escalation rule")

# spot-check known stress profile (INDC should be > NVTC on vulnerability)
indc_v = all_results["INDC"]["vulnerability"]["score"]
nvtc_v = all_results["NVTC"]["vulnerability"]["score"]
report("INDC_more_vulnerable_than_NVTC",
       PASS if indc_v > nvtc_v else FAIL,
       f"INDC={indc_v:.0f}, NVTC={nvtc_v:.0f}")

all_vulns = {cid: r["vulnerability"]["score"] for cid, r in all_results.items()}
top_v = max(all_vulns, key=all_vulns.get)
bot_v = min(all_vulns, key=all_vulns.get)
report("most_vulnerable_is_critical_company",
       PASS if top_v in ("INDC", "RETR") else WARN,
       f"max = {top_v}")
report("least_vulnerable_is_NVTC",
       PASS if bot_v == "NVTC" else WARN,
       f"min = {bot_v}")

# MDCO's controlled + dual-class structure should drive legal feasibility low
mdco_legal = all_results["MDCO"]["legal"]["legal_feasibility_score"]
report("MDCO_low_legal_feasibility",
       PASS if mdco_legal < 50 else FAIL,
       f"MDCO legal_feasibility={mdco_legal}")

crit = [cid for cid, r in all_results.items()
        if r["final_score"]["final_risk_level"] == "Critical"]
report("at_least_one_critical_company",
       PASS if crit else FAIL,
       f"crit={crit}")


# ----- Group 5: determinism -------------------------------------------------
print("\n[Group 5] Determinism across seeds and re-runs")

diffs = []
for cid in companies:
    r2 = run_company_analysis(cid, data)
    for top, sub in [("simulation", "p_activist_wins_1_plus"),
                     ("simulation", "p_activist_wins_2_plus"),
                     ("simulation", "p_proxy_vote"),
                     ("final_score", "activism_event_probability_12m"),
                     ("vulnerability", "score"),
                     ("fixability", "score")]:
        v1 = all_results[cid][top][sub]
        v2 = r2[top][sub]
        if abs(float(v1) - float(v2)) > 1e-9:
            diffs.append(f"{cid}.{top}.{sub}: {v1} vs {v2}")
report("deterministic_re_run",
       FAIL if diffs else PASS,
       "; ".join(diffs[:5]) if diffs
       else f"all {n} companies × 6 metrics identical")


# ----- Group 6: memo + war room output quality -----------------------------
print("\n[Group 6] Memo + war room output quality")

# Look for raw Python repr leaking into memo text
LEAK_PATTERNS = [r"<class '", r"<function ", r"<bound method",
                 r"object at 0x", r"NaN\b"]
leaks = defaultdict(list)
for cid, r in all_results.items():
    memo = r.get("board_memo", "")
    for pat in LEAK_PATTERNS:
        m = re.findall(pat, memo)
        if m:
            leaks[pat].extend([(cid, x) for x in m[:2]])
report("no_python_repr_leakage_in_memo",
       WARN if leaks else PASS,
       "; ".join(f"{p}: {s[:1]}" for p, s in leaks.items()) if leaks else "")

# memo length
memo_lens = {cid: len(r.get("board_memo", "")) for cid, r in all_results.items()}
too_short = [cid for cid, l in memo_lens.items() if l < 5000]
report("memo_length_reasonable",
       FAIL if too_short else PASS,
       f"too short: {too_short}" if too_short
       else f"avg={sum(memo_lens.values())/len(memo_lens):.0f} chars, "
            f"min={min(memo_lens.values())}, max={max(memo_lens.values())}")

# em-dashes signal "—" fallbacks; too many means missing data
em_counts = {cid: r.get("board_memo", "").count("—") for cid, r in all_results.items()}
worst_em = max(em_counts.values())
report("not_too_many_em_dashes",
       WARN if worst_em > 30 else PASS,
       f"some memos have many '—' fallbacks: "
       f"{ {c: n for c, n in em_counts.items() if n > 30} }" if worst_em > 30
       else f"max em-dashes in any memo: {worst_em}")

# compliance note must appear in every memo
no_compliance = [cid for cid, r in all_results.items()
                 if "legal advice" not in r.get("board_memo", "").lower()]
report("compliance_note_in_memo",
       FAIL if no_compliance else PASS,
       f"missing in: {no_compliance}" if no_compliance else "")

# war room sections all present & non-empty
wr_required = {"red_team_attack", "blue_team_defense", "board_qa",
               "investor_talking_points", "press_narrative"}
wr_issues = []
for cid, r in all_results.items():
    wr = r.get("war_room", {})
    for section in wr_required:
        if section not in wr:
            wr_issues.append(f"{cid}: missing {section}")
        else:
            content = wr[section]
            if isinstance(content, str) and len(content) < 100:
                wr_issues.append(f"{cid}.{section}: only {len(content)} chars")
            elif isinstance(content, list) and not content:
                wr_issues.append(f"{cid}.{section}: empty list")
report("war_room_sections_non_empty",
       WARN if wr_issues else PASS,
       "; ".join(wr_issues[:5]) if wr_issues
       else "all 5 sections × all companies non-empty")


# ----- Group 7: performance -------------------------------------------------
print("\n[Group 7] Performance")
slow = [(cid, t) for cid, t in timings.items() if t > 2.0]
report("each_company_under_2s",
       WARN if slow else PASS,
       str(slow) if slow
       else f"avg={sum(timings.values())/len(timings):.2f}s, "
            f"max={max(timings.values()):.2f}s")


# ----- Group 8: type contracts ----------------------------------------------
print("\n[Group 8] Type contracts")

# graphs must be JSON-serializable (we store them as node-link dicts)
non_serial = []
for cid, r in all_results.items():
    try:
        json.dumps(r["claim_graph"])
        json.dumps(r["shareholder_graph"])
    except (TypeError, ValueError) as e:
        non_serial.append(f"{cid}: {e}")
report("graphs_json_serializable",
       FAIL if non_serial else PASS,
       "; ".join(non_serial[:3]) if non_serial
       else "claim_graph + shareholder_graph json-safe for all companies")

# things that must be lists, must be lists
list_violations = []
for cid, r in all_results.items():
    for key in ("director_scores", "nominee_profiles", "theses",
                "activist_dna", "claim_attack_table", "claim_defense_table"):
        if not isinstance(r.get(key), list):
            list_violations.append(f"{cid}.{key}: {type(r.get(key)).__name__}")
report("lists_are_lists",
       FAIL if list_violations else PASS,
       "; ".join(list_violations[:5]) if list_violations else "")


# ----- Group 9: hidden errors -----------------------------------------------
print("\n[Group 9] Hidden errors")

hidden = []
for cid, r in all_results.items():
    hidden.extend(find_error_keys(r, cid))
report("no_hidden_error_keys",
       FAIL if hidden else PASS,
       "; ".join(hidden[:5]) if hidden else "")

# also look for "[Board memo generation error" / "War room generation error"
# fallback strings in the output - those mean memo/war-room raised somewhere
fallback_msgs = []
for cid, r in all_results.items():
    if isinstance(r.get("board_memo"), str) and "generation error" in r["board_memo"]:
        fallback_msgs.append(f"{cid}: memo error fallback")
    if isinstance(r.get("war_room"), dict) and "error" in r["war_room"]:
        fallback_msgs.append(f"{cid}: war room error fallback")
report("no_fallback_error_strings",
       FAIL if fallback_msgs else PASS,
       "; ".join(fallback_msgs) if fallback_msgs else "")


# ----- Group 10: settlement-game logic --------------------------------------
print("\n[Group 10] Settlement-game logic")

settle_issues = []
for cid, r in all_results.items():
    s = r.get("settlement") or {}
    best = s.get("best_option") or {}
    runner = s.get("runner_up_option") or {}
    if not best.get("option_name"):
        settle_issues.append(f"{cid}: no best option name")
    if not runner.get("option_name"):
        settle_issues.append(f"{cid}: no runner-up option name")
    bu, ru = best.get("utility_score"), runner.get("utility_score")
    if bu is not None and ru is not None and float(bu) < float(ru):
        settle_issues.append(f"{cid}: best utility ({bu}) < runner-up ({ru})")
report("settlement_logic_sound",
       FAIL if settle_issues else PASS,
       "; ".join(settle_issues[:5]) if settle_issues
       else "best ≥ runner-up utility, both named for all companies")


# ----- Group 11: director scoring -------------------------------------------
print("\n[Group 11] Director scoring")

dir_issues = []
for cid, r in all_results.items():
    dirs = r.get("director_scores") or []
    if not dirs:
        dir_issues.append(f"{cid}: no director scores")
        continue
    for d in dirs:
        if not d.get("name"):
            dir_issues.append(f"{cid}: director missing name")
        s = d.get("score")
        if s is None or not (0 <= float(s) <= 100):
            dir_issues.append(f"{cid}: {d.get('name')} score {s}")
n_dirs = sum(len(r.get("director_scores") or []) for r in all_results.values())
report("directors_well_formed",
       FAIL if dir_issues else PASS,
       "; ".join(dir_issues[:5]) if dir_issues
       else f"{n_dirs} director scores across {n} companies")


# ----- Group 12: coalition arithmetic ---------------------------------------
print("\n[Group 12] Coalition arithmetic")

coal_issues = []
for cid, r in all_results.items():
    c = r.get("coalition") or {}
    total = (float(c.get("expected_activist_vote_pct", 0) or 0)
             + float(c.get("expected_management_vote_pct", 0) or 0)
             + float(c.get("expected_abstain_pct", 0) or 0))
    # allow a couple pp of rounding slop
    if not (95 <= total <= 105):
        coal_issues.append(f"{cid}: a+m+abs = {total:.1f}")
report("coalition_sums_to_100",
       FAIL if coal_issues else PASS,
       "; ".join(coal_issues) if coal_issues else "")


# ----- Group 13: NVTC outperformer sanity -----------------------------------
print("\n[Group 13] NVTC outperformer sanity")

nvtc = all_results["NVTC"]
nvtc_issues = []
if nvtc["final_score"]["final_risk_level"] == "Critical":
    nvtc_issues.append("NVTC rated Critical (should not be)")
if nvtc["vulnerability"]["score"] > 60:
    nvtc_issues.append(f"NVTC vulnerability={nvtc['vulnerability']['score']} (>60)")
if nvtc["final_score"]["activism_event_probability_12m"] > 0.5:
    nvtc_issues.append(
        f"NVTC p_event_12m={nvtc['final_score']['activism_event_probability_12m']} (>0.5)"
    )
report("NVTC_outperformer_sanity",
       FAIL if nvtc_issues else PASS,
       "; ".join(nvtc_issues) if nvtc_issues
       else f"vuln={nvtc['vulnerability']['score']:.0f}, "
            f"risk={nvtc['final_score']['final_risk_level']}, "
            f"p12m={nvtc['final_score']['activism_event_probability_12m']:.2f}")


# ----- summary --------------------------------------------------------------
print("\n" + "=" * 50)
counts = Counter(r[1] for r in log)
print(f"Total checks: {len(log)}")
print(f"  {PASS}: {counts[PASS]}")
print(f"  {WARN}: {counts[WARN]}")
print(f"  {FAIL}: {counts[FAIL]}")

if counts[FAIL]:
    print("\nFAILURES:")
    for name, status, msg in log:
        if status == FAIL:
            print(f"  - {name}: {msg}")
    sys.exit(1)
if counts[WARN]:
    print("\nWARNINGS:")
    for name, status, msg in log:
        if status == WARN:
            print(f"  - {name}: {msg}")
sys.exit(0)
