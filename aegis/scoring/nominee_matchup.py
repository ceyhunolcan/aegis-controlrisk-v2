# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Nominee profile library + matchup scoring. Given the current board and
# the dominant thesis, pick the activist's best three nominees from the
# library and predict head-to-head win probability against incumbents.
#
# Win prob is heavily moderated by structural defenses - controlled
# company multiplies by 0.45, dual-class by 0.55, classified board by 0.75.
# These compound, so a controlled dual-class classified-board company
# (MDCO is close to this) effectively can't be unseated regardless of
# how good the nominees are.
import math

from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100
)


NOMINEE_PROFILES = [
    {
        "nominee_id": "N01",
        "profile_name": "Former CEO of public-company peer",
        "background": "Former CEO of a publicly traded peer in the same sector with track record of margin/TSR improvement.",
        "expertise": {"capital_allocation": 80, "operations": 85, "sector": 90, "tech": 50, "climate": 50, "governance": 70},
        "stature_score": 90,
        "proxy_advisor_appeal": 85,
        "shareholder_credibility": 88,
    },
    {
        "nominee_id": "N02",
        "profile_name": "Former COO / operational turnaround",
        "background": "Operating executive who led margin recovery at a $5B+ industrial or consumer business.",
        "expertise": {"capital_allocation": 70, "operations": 95, "sector": 75, "tech": 45, "climate": 40, "governance": 60},
        "stature_score": 80,
        "proxy_advisor_appeal": 82,
        "shareholder_credibility": 82,
    },
    {
        "nominee_id": "N03",
        "profile_name": "Capital allocation specialist",
        "background": "Former PE operating partner / former CFO known for disciplined buybacks, divestitures, and ROIC focus.",
        "expertise": {"capital_allocation": 95, "operations": 70, "sector": 65, "tech": 40, "climate": 45, "governance": 70},
        "stature_score": 78,
        "proxy_advisor_appeal": 80,
        "shareholder_credibility": 86,
    },
    {
        "nominee_id": "N04",
        "profile_name": "Former CFO / audit specialist",
        "background": "Former CFO with strong audit committee experience and clean disclosure track record.",
        "expertise": {"capital_allocation": 80, "operations": 65, "sector": 65, "tech": 50, "climate": 45, "governance": 80},
        "stature_score": 76,
        "proxy_advisor_appeal": 85,
        "shareholder_credibility": 80,
    },
    {
        "nominee_id": "N05",
        "profile_name": "Restructuring / strategic alternatives expert",
        "background": "M&A advisor or restructuring CEO who has led split-ups, spin-offs, or sales of complex companies.",
        "expertise": {"capital_allocation": 88, "operations": 70, "sector": 60, "tech": 50, "climate": 45, "governance": 70},
        "stature_score": 80,
        "proxy_advisor_appeal": 70,
        "shareholder_credibility": 82,
    },
    {
        "nominee_id": "N06",
        "profile_name": "Technology platform executive",
        "background": "Former CTO/CPO of a scaled software or platform company; brings digital transformation lens.",
        "expertise": {"capital_allocation": 60, "operations": 75, "sector": 65, "tech": 95, "climate": 55, "governance": 65},
        "stature_score": 74,
        "proxy_advisor_appeal": 75,
        "shareholder_credibility": 78,
    },
    {
        "nominee_id": "N07",
        "profile_name": "Climate / energy transition operator",
        "background": "Executive who has run a major energy transition / decarbonization program profitably.",
        "expertise": {"capital_allocation": 70, "operations": 75, "sector": 80, "tech": 60, "climate": 95, "governance": 70},
        "stature_score": 78,
        "proxy_advisor_appeal": 88,
        "shareholder_credibility": 82,
    },
    {
        "nominee_id": "N08",
        "profile_name": "Governance / former GC",
        "background": "Former General Counsel of a Fortune 100 company with deep governance and proxy experience.",
        "expertise": {"capital_allocation": 60, "operations": 60, "sector": 65, "tech": 55, "climate": 55, "governance": 95},
        "stature_score": 72,
        "proxy_advisor_appeal": 90,
        "shareholder_credibility": 78,
    },
    {
        "nominee_id": "N09",
        "profile_name": "Healthcare / regulated industries operator",
        "background": "Former CEO/President of a regulated healthcare or financial company with clean compliance record.",
        "expertise": {"capital_allocation": 72, "operations": 80, "sector": 90, "tech": 60, "climate": 50, "governance": 78},
        "stature_score": 80,
        "proxy_advisor_appeal": 80,
        "shareholder_credibility": 82,
    },
]


def generate_nominee_profiles():
    """Return the canonical list of activist nominee profiles."""
    return [dict(p) for p in NOMINEE_PROFILES]


def _profile_for_sector(sector):
    """Pick the most sector-aligned profile as a recommendation default."""
    s = (sector or "").lower()
    if "energy" in s or "utilities" in s:
        return NOMINEE_PROFILES[6]  # Climate/transition
    if "tech" in s:
        return NOMINEE_PROFILES[5]  # Tech platform
    if "health" in s:
        return NOMINEE_PROFILES[8]  # Healthcare
    if "financ" in s or "bank" in s:
        return NOMINEE_PROFILES[7]  # Governance/GC
    if "industrial" in s or "materials" in s:
        return NOMINEE_PROFILES[1]  # COO turnaround
    return NOMINEE_PROFILES[2]  # Capital allocation default


def score_nominee_vs_director(
    nominee, director_score_row, company):
    """Score a head-to-head matchup. Returns probability nominee wins seat."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()

    # Director replaceability baseline
    d_score = safe_float(safe_get(director_score_row, "score", 50), 50)

    # Nominee strength: blended stature + proxy advisor + sector expertise + credibility
    sector = str(safe_get(company, "sector", "")).lower()
    sector_exp = safe_float(nominee.get("expertise", {}).get("sector", 60), 60)
    if "energy" in sector:
        sector_exp = safe_float(nominee.get("expertise", {}).get("climate", 50), 50) * 0.5 + sector_exp * 0.5
    elif "tech" in sector:
        sector_exp = safe_float(nominee.get("expertise", {}).get("tech", 50), 50) * 0.5 + sector_exp * 0.5

    nominee_strength = (
        0.30 * safe_float(nominee.get("stature_score", 70), 70) +
        0.25 * safe_float(nominee.get("proxy_advisor_appeal", 70), 70) +
        0.25 * safe_float(nominee.get("shareholder_credibility", 70), 70) +
        0.20 * sector_exp
    )

    # Win probability blends director vulnerability + nominee strength
    # If director has high replaceability AND nominee is strong, probability is high
    base = 0.5 * (d_score / 100.0) + 0.5 * (nominee_strength / 100.0)

    # Adjust for company governance
    if bool(safe_get(company, "controlled_company_flag", False)):
        base *= 0.45  # Hard to win seats at controlled company
    elif bool(safe_get(company, "dual_class_flag", False)):
        base *= 0.55
    if bool(safe_get(company, "classified_board", False)):
        base *= 0.75

    # Apply non-linear bump for committee chair targets
    if bool(safe_get(director_score_row, "is_committee_chair", False)):
        base = min(1.0, base * 1.10)

    win_prob = clamp(base * 100, 0, 100)

    # Differential framing
    differential = (nominee_strength - (100 - d_score))  # nominee strength vs director "entrenchment"

    return {
        "nominee_id": nominee.get("nominee_id"),
        "nominee_name": nominee.get("profile_name"),
        "director_id": safe_get(director_score_row, "director_id", ""),
        "director_name": safe_get(director_score_row, "name", ""),
        "nominee_strength_score": round(nominee_strength, 1),
        "director_replaceability_score": round(d_score, 1),
        "differential": round(differential, 1),
        "win_probability_pct": round(win_prob, 1),
        "rationale": (
            f"Nominee profile '{nominee.get('profile_name')}' against director "
            f"'{safe_get(director_score_row, 'name', '')}' yields a "
            f"{win_prob:.0f}% modeled win probability."
        ),
    }


def optimize_activist_slate(
    director_scores,
    company,
    max_slate_size = 3):
    """Choose the optimal activist slate (which director to target with which nominee profile)."""
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if company is None:
        company = {}

    if not director_scores:
        return {
            "slate": [],
            "expected_seats_won": 0.0,
            "slate_summary": "No director data available.",
            "max_slate_size": max_slate_size,
            "nominee_profiles": generate_nominee_profiles(),
        }

    profiles = generate_nominee_profiles()

    # For each top vulnerable director, find best-matched profile
    candidates = []
    top_targets = director_scores[: min(len(director_scores), max_slate_size + 3)]
    used_profiles = set()
    for d in top_targets:
        matchups = []
        for p in profiles:
            m = score_nominee_vs_director(p, d, company)
            matchups.append(m)
        # Best matchup not yet used
        matchups.sort(key=lambda x: x["win_probability_pct"], reverse=True)
        chosen = None
        for m in matchups:
            if m["nominee_id"] not in used_profiles:
                chosen = m
                break
        if chosen is None:
            chosen = matchups[0]
        used_profiles.add(chosen["nominee_id"])
        candidates.append(chosen)

    # Top-N by win probability
    candidates.sort(key=lambda x: x["win_probability_pct"], reverse=True)
    slate = candidates[:max_slate_size]
    expected_seats = sum(c["win_probability_pct"] / 100.0 for c in slate)

    summary = (
        f"Optimized {len(slate)}-seat slate targets {', '.join(c['director_name'] for c in slate)}. "
        f"Expected seats won (sum of probabilities): {expected_seats:.2f} of {len(slate)}."
    )

    return {
        "slate": slate,
        "expected_seats_won": round(expected_seats, 2),
        "max_slate_size": max_slate_size,
        "slate_summary": summary,
        "nominee_profiles": profiles,
        "all_matchups": candidates,
    }
