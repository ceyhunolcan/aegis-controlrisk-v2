# Copyright (c) 2026. All rights reserved. Proprietary. See LICENSE.
# Thesis generation. Produces 8 candidate activist theses (board refresh,
# margin improvement, breakup, comp alignment, climate/transition, CEO
# succession, M&A discipline, balance sheet), scores each on 8 weighted
# components, and picks the strongest. Evidence + peer benchmark
# strength dominate - a thesis without a clean public-comp anchor is
# very hard to push past PA gatekeepers.
from typing import Dict, List

from ..utils.normalization import (
    clamp, safe_float, safe_get, normalize_0_100, weighted_score
)


WEIGHTS = {
    "evidence_strength": 0.18,
    "peer_benchmark_strength": 0.16,
    "financial_upside_quantification": 0.15,
    "board_level_relevance": 0.13,
    "shareholder_appeal": 0.12,
    "proxy_advisor_compatibility": 0.10,
    "media_simplicity": 0.08,
    "rebuttability_resistance": 0.08,
}


# Each thesis has signal extractors that turn vulnerability components into score ingredients.
def _signal(comps, key, default = 50.0):
    return clamp(safe_float(safe_get(comps, key, default), default))


def _generate_candidate_theses(
    company,
    fin,
    vuln,
    fix):
    comps = vuln.get("components", {}) if isinstance(vuln, dict) else {}
    fix_score = safe_float(safe_get(fix, "score", 50), 50) if isinstance(fix, dict) else 50.0
    sector = str(safe_get(company, "sector", ""))

    theses: List[Dict] = []

    # 1. Board Refresh + Capital Allocation Discipline
    cap = _signal(comps, "capital_allocation_weakness")
    gov = _signal(comps, "governance_weakness")
    th1 = {
        "name": "Board Refresh + Capital Allocation Discipline",
        "evidence_strength": clamp(0.5 * cap + 0.3 * _signal(comps, "tsr_underperformance") + 0.2 * gov),
        "peer_benchmark_strength": clamp(0.6 * _signal(comps, "valuation_discount") + 0.4 * cap),
        "financial_upside_quantification": clamp(0.6 * _signal(comps, "roic_margin_gap") + 0.4 * cap),
        "board_level_relevance": 88.0,
        "shareholder_appeal": clamp(0.5 * _signal(comps, "prior_shareholder_dissent") + 0.5 * cap),
        "proxy_advisor_compatibility": 75.0,
        "media_simplicity": 70.0,
        "rebuttability_resistance": clamp(70 - 0.2 * fix_score + 0.3 * cap),
        "recommended_ask": [
            "Refresh 2 long-tenured directors with capital-allocation experts",
            "Publish a 3-year ROIC/FCF framework with thresholds",
            "Add ROIC and FCF metrics to executive compensation",
        ],
        "estimated_upside_range": "15–30%",
        "activist_attack_memo": "The board has failed to enforce capital discipline. New independent directors with capital-allocation track records can re-anchor the company's value framework.",
        "management_weakness": "Capex/M&A history suggests the board has not held management accountable for return on invested capital.",
        "evidence_bullets": [
            "ROIC trails peers by a measurable margin",
            "M&A writeoffs / capex intensity above peer level",
            "Stock has underperformed over multiple horizons",
        ],
        "risks_to_thesis": [
            "Management may pre-empt by adopting ROIC compensation metric",
            "Recent operational momentum could blunt the thesis",
        ],
    }
    theses.append(th1)

    # 2. Margin Improvement / Operational Efficiency
    mgn = _signal(comps, "roic_margin_gap")
    th2 = {
        "name": "Margin Improvement / Operational Efficiency",
        "evidence_strength": clamp(0.7 * mgn + 0.3 * _signal(comps, "strategic_confusion")),
        "peer_benchmark_strength": clamp(0.9 * mgn),
        "financial_upside_quantification": clamp(0.8 * mgn + 0.2 * _signal(comps, "tsr_underperformance")),
        "board_level_relevance": 70.0,
        "shareholder_appeal": clamp(0.5 * mgn + 0.5 * _signal(comps, "valuation_discount")),
        "proxy_advisor_compatibility": 55.0,
        "media_simplicity": 78.0,
        "rebuttability_resistance": clamp(60 - 0.25 * fix_score + 0.4 * mgn),
        "recommended_ask": [
            "Disclose a credible 200-400bps EBITDA margin improvement plan",
            "Appoint a board-level operating committee",
            "Add an operationally experienced director to the slate",
        ],
        "estimated_upside_range": "10–25%",
        "activist_attack_memo": "A persistent EBITDA margin gap to peers is the clearest indicator that the operating model is under-managed.",
        "management_weakness": "Management has not closed the peer margin gap despite multi-year guidance.",
        "evidence_bullets": [
            f"EBITDA margin lags peers by {abs(safe_float(safe_get(fin, 'ebitda_margin_gap_vs_peer', 0), 0)):.1f}pp",
            "Persistent guidance/earnings miss pattern",
        ],
        "risks_to_thesis": [
            "Cyclical industries may have transient margin pressure",
            "If management announces a margin program first, the activist loses initiative",
        ],
    }
    theses.append(th2)

    # 3. Breakup / Strategic Alternatives
    is_conglomerate = str(safe_get(company, "industry", "")).lower().find("diversified") >= 0
    breakup_signal = 80.0 if is_conglomerate else 45.0
    th3 = {
        "name": "Breakup or Strategic Alternatives",
        "evidence_strength": clamp(0.5 * _signal(comps, "valuation_discount") + 0.3 * breakup_signal + 0.2 * _signal(comps, "capital_allocation_weakness")),
        "peer_benchmark_strength": clamp(0.6 * _signal(comps, "valuation_discount") + 0.4 * breakup_signal),
        "financial_upside_quantification": clamp(0.55 * breakup_signal + 0.45 * _signal(comps, "valuation_discount")),
        "board_level_relevance": 75.0,
        "shareholder_appeal": clamp(0.5 * _signal(comps, "valuation_discount") + 0.5 * breakup_signal),
        "proxy_advisor_compatibility": 50.0,
        "media_simplicity": 65.0,
        "rebuttability_resistance": clamp(45 + 0.3 * breakup_signal),
        "recommended_ask": [
            "Form a strategic review committee with independent advisors",
            "Evaluate divestitures, separation, or take-private bids",
            "Disclose sum-of-the-parts analysis",
        ],
        "estimated_upside_range": "20–40%",
        "activist_attack_memo": "The conglomerate discount is a structural problem. A strategic review unlocks trapped value.",
        "management_weakness": "Persistent discount suggests the market does not credit the synergy story.",
        "evidence_bullets": [
            "EV/EBITDA discount to peers is substantial",
            "Sum-of-the-parts likely exceeds market cap",
        ],
        "risks_to_thesis": [
            "Tax leakage or capital structure complexity can reduce realized value",
            "Market windows for M&A may close",
        ],
    }
    theses.append(th3)

    # 4. Compensation Alignment
    sop = safe_float(safe_get(fin, "say_on_pay_support_pct", 90), 90)
    sop_signal = normalize_0_100(sop, 70, 95, inverse=True)
    th4 = {
        "name": "Compensation Alignment",
        "evidence_strength": clamp(0.8 * sop_signal + 0.2 * _signal(comps, "tsr_underperformance")),
        "peer_benchmark_strength": clamp(0.5 * sop_signal + 0.5 * _signal(comps, "tsr_underperformance")),
        "financial_upside_quantification": 45.0,
        "board_level_relevance": 90.0,
        "shareholder_appeal": clamp(0.7 * sop_signal + 0.3 * _signal(comps, "prior_shareholder_dissent")),
        "proxy_advisor_compatibility": 92.0,
        "media_simplicity": 80.0,
        "rebuttability_resistance": clamp(50 + 0.3 * sop_signal),
        "recommended_ask": [
            "Re-design CEO compensation around relative TSR and ROIC",
            "Cap mega-grants and align vesting with multi-year performance",
            "Refresh the compensation committee chair",
        ],
        "estimated_upside_range": "5–15% (governance discount closing)",
        "activist_attack_memo": "Pay outcomes are detached from shareholder outcomes. The compensation committee has been asleep.",
        "management_weakness": "Repeated low Say-on-Pay support signals shareholder revolt against pay structure.",
        "evidence_bullets": [
            f"Say-on-Pay support at {sop:.0f}% (peers > 90%)",
            "Pay-for-performance disconnect over rolling 3-year period",
        ],
        "risks_to_thesis": [
            "Single-issue thesis can be neutralized by quick comp reform",
        ],
    }
    theses.append(th4)

    # 5. Climate / Transition Risk
    is_carbon = sector in {"Energy", "Materials", "Utilities"}
    transition_signal = 80.0 if is_carbon else 30.0
    th5 = {
        "name": "Climate / Transition Risk",
        "evidence_strength": clamp(0.7 * transition_signal + 0.3 * _signal(comps, "narrative_strength")),
        "peer_benchmark_strength": clamp(0.6 * transition_signal),
        "financial_upside_quantification": clamp(0.5 * transition_signal),
        "board_level_relevance": clamp(0.4 * transition_signal + 30),
        "shareholder_appeal": clamp(0.6 * transition_signal + 20),
        "proxy_advisor_compatibility": clamp(0.5 * transition_signal + 35),
        "media_simplicity": 88.0 if is_carbon else 40.0,
        "rebuttability_resistance": 55.0 if is_carbon else 30.0,
        "recommended_ask": [
            "Appoint a climate / transition-expertise director",
            "Publish a credible transition capital plan",
            "Disclose Scope 1-3 emissions trajectory with interim targets",
        ],
        "estimated_upside_range": "5–18% (re-rating to transition leaders)",
        "activist_attack_memo": "The board lacks credible energy-transition expertise. Capital allocation must reflect the long-term cost of carbon.",
        "management_weakness": "No transition-expert director means the board cannot credibly evaluate trade-offs.",
        "evidence_bullets": [
            "No transition-expert director on board",
            "Capex skewed to legacy assets",
        ] if is_carbon else ["Limited applicability outside carbon-exposed sectors"],
        "risks_to_thesis": [
            "Cyclical commodity strength can mute relevance",
            "Returns-based investors may discount narrative",
        ],
    }
    theses.append(th5)

    # 6. CEO Succession / Leadership Accountability
    ceo_chair = bool(safe_get(company, "ceo_chair_combined", False))
    th6 = {
        "name": "CEO Succession / Leadership Accountability",
        "evidence_strength": clamp(0.5 * _signal(comps, "tsr_underperformance") + 0.3 * _signal(comps, "strategic_confusion") + 0.2 * sop_signal),
        "peer_benchmark_strength": clamp(0.7 * _signal(comps, "tsr_underperformance") + 0.3 * _signal(comps, "valuation_discount")),
        "financial_upside_quantification": 55.0,
        "board_level_relevance": 95.0,
        "shareholder_appeal": clamp(0.5 * _signal(comps, "tsr_underperformance") + 0.5 * sop_signal),
        "proxy_advisor_compatibility": 65.0,
        "media_simplicity": 75.0,
        "rebuttability_resistance": clamp(40 + 0.3 * _signal(comps, "tsr_underperformance")) + (5 if ceo_chair else 0),
        "recommended_ask": [
            "Separate CEO and Chair roles",
            "Begin formal CEO succession process",
            "Refresh the governance committee",
        ],
        "estimated_upside_range": "10–25%",
        "activist_attack_memo": "Persistent underperformance under the current CEO requires accountability. The board has not acted.",
        "management_weakness": "Multi-year TSR underperformance under unchanged leadership.",
        "evidence_bullets": [
            "Multi-year TSR underperformance",
            "Combined CEO/Chair structure removes a layer of accountability",
        ],
        "risks_to_thesis": [
            "CEO transitions create execution risk",
            "Personal-attack framing can backfire with passive holders",
        ],
    }
    theses.append(th6)

    # 7. M&A Discipline
    th7 = {
        "name": "M&A Discipline",
        "evidence_strength": clamp(0.8 * safe_float(safe_get(fin, "mna_writeoff_history_score", 50), 50) + 0.2 * _signal(comps, "tsr_underperformance")),
        "peer_benchmark_strength": clamp(0.7 * safe_float(safe_get(fin, "mna_writeoff_history_score", 50), 50)),
        "financial_upside_quantification": 60.0,
        "board_level_relevance": 80.0,
        "shareholder_appeal": clamp(safe_float(safe_get(fin, "mna_writeoff_history_score", 50), 50)),
        "proxy_advisor_compatibility": 70.0,
        "media_simplicity": 72.0,
        "rebuttability_resistance": clamp(safe_float(safe_get(fin, "mna_writeoff_history_score", 50), 50) - 10),
        "recommended_ask": [
            "Adopt an M&A discipline framework (size limits, IRR thresholds)",
            "Require board-supermajority for transactions above defined thresholds",
            "Independent post-mortem on prior deals",
        ],
        "estimated_upside_range": "8–20%",
        "activist_attack_memo": "Multiple writedowns indicate the board has not enforced M&A discipline.",
        "management_weakness": "Acquisition history shows value destruction.",
        "evidence_bullets": ["Prior M&A writeoffs", "Goodwill ratio elevated"],
        "risks_to_thesis": [
            "Cyclical writedowns can be defended as one-time",
        ],
    }
    theses.append(th7)

    # 8. Balance Sheet / Capital Return Optimization
    lev_signal = normalize_0_100(safe_float(safe_get(fin, "leverage_vs_peer", 0), 0), -1.0, 2.0)
    fcfy = safe_float(safe_get(fin, "fcf_yield_vs_peer", 0), 0)
    th8 = {
        "name": "Balance Sheet / Capital Return Optimization",
        "evidence_strength": clamp(0.6 * _signal(comps, "valuation_discount") + 0.4 * normalize_0_100(-fcfy, -4, 6)),
        "peer_benchmark_strength": clamp(0.5 * _signal(comps, "valuation_discount") + 0.5 * lev_signal),
        "financial_upside_quantification": 70.0,
        "board_level_relevance": 75.0,
        "shareholder_appeal": clamp(0.6 * _signal(comps, "prior_shareholder_dissent") + 0.4 * _signal(comps, "valuation_discount")),
        "proxy_advisor_compatibility": 60.0,
        "media_simplicity": 70.0,
        "rebuttability_resistance": 40.0,
        "recommended_ask": [
            "Announce a $X buyback authorization scaled to free cash flow",
            "Optimize the dividend to match through-cycle FCF",
            "Term-out maturities and reduce excess cash drag",
        ],
        "estimated_upside_range": "8–18%",
        "activist_attack_memo": "Excess balance sheet capacity is not being deployed for shareholders.",
        "management_weakness": "Capital is trapped at low return.",
        "evidence_bullets": [
            "FCF yield gap to peers",
            "Below-peer leverage with no announced capital plan",
        ],
        "risks_to_thesis": [
            "Rising rate environment can change calculus",
            "Cyclical companies may legitimately preserve flexibility",
        ],
    }
    theses.append(th8)

    return theses


def _score_thesis(t):
    """Apply the credibility weighting to a candidate thesis."""
    components = {k: clamp(safe_float(t.get(k, 50), 50)) for k in WEIGHTS.keys()}
    score = weighted_score(components, WEIGHTS)
    out = dict(t)
    out["score"] = score
    out["shareholder_resonance"] = components["shareholder_appeal"]
    out["proxy_advisor_compatibility"] = components["proxy_advisor_compatibility"]
    out["rebuttability_score"] = clamp(100 - components["rebuttability_resistance"])
    return out


def generate_theses(
    company,
    financials,
    vulnerability_result,
    fixability_result,
    activist_dna_result = None):
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    if hasattr(financials, "model_dump"):
        financials = financials.model_dump()

    candidates = _generate_candidate_theses(company, financials,
                                            vulnerability_result, fixability_result)
    scored = [_score_thesis(t) for t in candidates]
    scored.sort(key=lambda x: x["score"], reverse=True)
    # If a top activist archetype is ESG/transition, lift transition thesis a touch
    if activist_dna_result:
        top = activist_dna_result[0] if isinstance(activist_dna_result, list) and activist_dna_result else None
        if top and "ESG" in str(top.get("name", "")).upper() + str(top.get("likely_campaign_style", "")).upper():
            for t in scored:
                if t["name"] == "Climate / Transition Risk":
                    t["score"] = clamp(t["score"] + 6)
            scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def select_primary_thesis(theses):
    if not theses:
        # Safe neutral fallback
        return {
            "name": "Generic Board Refresh + Capital Discipline",
            "score": 50.0,
            "recommended_ask": ["Refresh board with capital-allocation expertise"],
            "estimated_upside_range": "5-15%",
            "activist_attack_memo": "Limited evidence available; baseline thesis.",
            "management_weakness": "Insufficient data to identify a specific weakness.",
            "evidence_bullets": ["No conclusive evidence in input data."],
            "risks_to_thesis": ["Insufficient data."],
            "shareholder_resonance": 50.0,
            "proxy_advisor_compatibility": 50.0,
            "rebuttability_score": 50.0,
        }
    return theses[0]
