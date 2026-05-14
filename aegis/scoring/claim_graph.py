# Builds the activist claim DAG. Each claim is a (text, type, scoring) tuple
# wired together so we can rank them by power (evidence × resonance × simplicity
# - rebuttability) and surface the top-N for memo writing.
#
# The graph itself is exported via json_graph.node_link_data so it
# round-trips cleanly to JSON - the dashboard renders it from there.
from typing import List
import networkx as nx
from networkx.readwrite import json_graph

from ..utils.normalization import clamp, safe_float, safe_get


# Catalogue of the eight stock activist claim templates. The full set isn't
# used for every company - _select_claims_for_thesis() picks which ones fit
# the dominant thesis.
_CLAIM_TEMPLATES = {
    "financial_underperformance": (
        "The company has materially underperformed peers on TSR for 3+ years.",
        "financial_underperformance",
        85,
    ),
    "valuation_discount": (
        "Shares trade at a structural valuation discount to peers.",
        "valuation_discount",
        80,
    ),
    "capital_allocation": (
        "Capital allocation has destroyed value through over-capex or value-destroying M&A.",
        "capital_allocation",
        75,
    ),
    "board_skills": (
        "The board lacks the specific skills (capital allocation, sector, transition) needed.",
        "board_skills",
        78,
    ),
    "governance": (
        "Governance structures shield management from accountability.",
        "governance",
        70,
    ),
    "compensation": (
        "Executive compensation is not aligned with shareholder outcomes.",
        "compensation",
        82,
    ),
    "esg_transition": (
        "The board lacks credible climate/transition expertise and capital planning.",
        "esg_transition",
        65,
    ),
    "strategic_alternatives": (
        "A strategic review or breakup would unlock value not credited by the market.",
        "strategic_alternatives",
        68,
    ),
}


def _select_claims_for_thesis(primary_thesis, vuln_comps, company):
    """Pick which claim keys are most relevant given the thesis and company."""
    name = str(primary_thesis.get("name", "")).lower() if primary_thesis else ""
    keys: List[str] = ["financial_underperformance", "valuation_discount"]
    if "capital allocation" in name or "discipline" in name:
        keys += ["capital_allocation", "board_skills"]
    if "margin" in name or "operational" in name:
        keys += ["capital_allocation", "board_skills"]
    if "breakup" in name or "strategic alternatives" in name:
        keys += ["strategic_alternatives", "capital_allocation"]
    if "compensation" in name:
        keys += ["compensation", "governance"]
    if "climate" in name or "transition" in name:
        keys += ["esg_transition", "board_skills"]
    if "ceo" in name or "leadership" in name:
        keys += ["governance", "compensation"]
    if "m&a" in name or "mna" in name:
        keys += ["capital_allocation", "board_skills"]
    if "balance sheet" in name or "capital return" in name:
        keys += ["capital_allocation"]
    # Governance is always relevant for controlled / dual-class
    if safe_get(company, "controlled_company_flag", False) or safe_get(company, "dual_class_flag", False):
        keys.append("governance")
    # Always include at least board_skills + compensation
    keys += ["board_skills", "compensation"]
    # Deduplicate preserving order
    seen = set()
    out = []
    for k in keys:
        if k not in seen and k in _CLAIM_TEMPLATES:
            seen.add(k)
            out.append(k)
    return out


def _score_claim(
    key,
    primary_thesis,
    vuln_comps,
    company,
    director_scores):
    text, ctype, simplicity = _CLAIM_TEMPLATES[key]
    th_score = safe_float(safe_get(primary_thesis, "score", 50), 50)

    # Base evidence strength per claim type
    if key == "financial_underperformance":
        evidence = clamp(safe_float(safe_get(vuln_comps, "tsr_underperformance", 50), 50))
    elif key == "valuation_discount":
        evidence = clamp(safe_float(safe_get(vuln_comps, "valuation_discount", 50), 50))
    elif key == "capital_allocation":
        evidence = clamp(safe_float(safe_get(vuln_comps, "capital_allocation_weakness", 50), 50))
    elif key == "board_skills":
        # Tied to avg director risk
        if director_scores:
            avg_risk = sum(d.get("score", 50) for d in director_scores) / max(1, len(director_scores))
        else:
            avg_risk = 55.0
        evidence = clamp(avg_risk)
    elif key == "governance":
        evidence = clamp(safe_float(safe_get(vuln_comps, "governance_weakness", 50), 50))
    elif key == "compensation":
        evidence = clamp(safe_float(safe_get(vuln_comps, "prior_shareholder_dissent", 50), 50))
    elif key == "esg_transition":
        sector = str(safe_get(company, "sector", ""))
        base = 70 if sector in {"Energy", "Materials", "Utilities"} else 35
        evidence = clamp(base + 0.3 * safe_float(safe_get(vuln_comps, "narrative_strength", 50), 50) - 15)
    elif key == "strategic_alternatives":
        is_conglomerate = "diversified" in str(safe_get(company, "industry", "")).lower()
        evidence = clamp((70 if is_conglomerate else 40) + 0.2 * safe_float(safe_get(vuln_comps, "valuation_discount", 50), 50))
    else:
        evidence = 50.0

    # Shareholder resonance (heuristic per claim type)
    sh_resonance = {
        "financial_underperformance": 88,
        "valuation_discount": 80,
        "capital_allocation": 78,
        "board_skills": 72,
        "governance": 70,
        "compensation": 75,
        "esg_transition": 55,
        "strategic_alternatives": 78,
    }.get(key, 60)

    # Proxy advisor resonance
    pa_resonance = {
        "financial_underperformance": 78,
        "valuation_discount": 60,
        "capital_allocation": 68,
        "board_skills": 80,
        "governance": 88,
        "compensation": 92,
        "esg_transition": 70,
        "strategic_alternatives": 55,
    }.get(key, 60)

    # Rebuttability: how easily can management neutralize this claim?
    rebut = {
        "financial_underperformance": 30,  # hard to rebut: numbers are numbers
        "valuation_discount": 55,  # rebut with "patience"
        "capital_allocation": 45,
        "board_skills": 55,
        "governance": 45,
        "compensation": 38,
        "esg_transition": 50,
        "strategic_alternatives": 70,  # easily rebut: "we considered, no clear path"
    }.get(key, 50)

    # Board accountability: how directly does it implicate the board?
    board_acc = {
        "financial_underperformance": 60,
        "valuation_discount": 50,
        "capital_allocation": 80,
        "board_skills": 95,
        "governance": 90,
        "compensation": 92,
        "esg_transition": 75,
        "strategic_alternatives": 65,
    }.get(key, 60)

    # Claim Power Score
    cps = clamp(0.25 * evidence
                + 0.20 * sh_resonance
                + 0.15 * pa_resonance
                + 0.15 * board_acc
                + 0.15 * simplicity
                - 0.10 * rebut)

    defense_priority = clamp(0.7 * cps + 0.3 * board_acc)

    return {
        "claim_id": key,
        "claim_text": text,
        "claim_type": ctype,
        "evidence_strength": evidence,
        "shareholder_resonance": sh_resonance,
        "proxy_advisor_resonance": pa_resonance,
        "rebuttability": rebut,
        "board_accountability": board_acc,
        "simplicity": simplicity,
        "claim_power_score": cps,
        "defense_priority": defense_priority,
    }


def _affected_shareholder_groups(claim_type):
    if claim_type in {"financial_underperformance", "valuation_discount", "strategic_alternatives"}:
        return ["Active Value Funds", "Hedge Funds", "Retail"]
    if claim_type in {"governance", "compensation"}:
        return ["Pension Funds", "Sovereign Wealth", "Passive Index Funds"]
    if claim_type == "esg_transition":
        return ["Pension Funds", "ESG Allocators", "Sovereign Wealth"]
    if claim_type == "board_skills":
        return ["Passive Index Funds", "Pension Funds", "Active Value Funds"]
    if claim_type == "capital_allocation":
        return ["Active Value Funds", "Hedge Funds", "Pension Funds"]
    return ["Active Value Funds"]


def _exposed_directors(claim_type, director_scores):
    """Return list of directors most exposed to this claim."""
    if not director_scores:
        return []
    if claim_type == "compensation":
        cands = [d for d in director_scores if "compensation" in str(d.get("name", "")).lower() or
                 d.get("score", 0) >= 60]
    elif claim_type == "governance":
        cands = [d for d in director_scores if d.get("score", 0) >= 55]
    elif claim_type == "board_skills":
        cands = [d for d in director_scores if d.get("score", 0) >= 60]
    elif claim_type == "capital_allocation":
        cands = [d for d in director_scores if d.get("score", 0) >= 55]
    elif claim_type == "esg_transition":
        cands = [d for d in director_scores if d.get("score", 0) >= 50]
    else:
        cands = [d for d in director_scores if d.get("score", 0) >= 60]
    # Top 3 by score
    cands = sorted(cands, key=lambda x: x.get("score", 0), reverse=True)[:3]
    return [{"director_id": d.get("director_id"), "name": d.get("name"),
             "score": d.get("score")} for d in cands]


def _recommended_defenses(claim_type):
    if claim_type == "financial_underperformance":
        return ["Investor day re-anchoring the strategy",
                "Highlight forward operating momentum",
                "Top-quartile TSR program"]
    if claim_type == "valuation_discount":
        return ["Capital return acceleration",
                "Re-segment financial reporting",
                "Publish sum-of-the-parts"]
    if claim_type == "capital_allocation":
        return ["Adopt formal ROIC/capex framework",
                "Add ROIC to executive compensation",
                "Halt low-return capex"]
    if claim_type == "board_skills":
        return ["Refresh 1-2 directors with required expertise",
                "Independent board skills matrix disclosure"]
    if claim_type == "governance":
        return ["Separate CEO/Chair",
                "Sunset dual-class structure (where feasible)",
                "Declassify board"]
    if claim_type == "compensation":
        return ["Re-design comp around relative TSR / ROIC",
                "Refresh comp committee chair",
                "Cap mega-grants"]
    if claim_type == "esg_transition":
        return ["Appoint transition-expert director",
                "Publish credible transition capital plan",
                "Disclose Scope 1-3 trajectory"]
    if claim_type == "strategic_alternatives":
        return ["Form strategic review committee",
                "Engage advisors to assess alternatives",
                "Publish independent SOTP"]
    return ["Engage shareholders proactively"]


def build_claim_graph(
    company,
    primary_thesis,
    vulnerability,
    fixability,
    director_scores = None):
    if hasattr(company, "model_dump"):
        company = company.model_dump()
    director_scores = director_scores or []
    vuln_comps = vulnerability.get("components", {}) if isinstance(vulnerability, dict) else {}

    claim_keys = _select_claims_for_thesis(primary_thesis, vuln_comps, company)
    claims = [_score_claim(k, primary_thesis, vuln_comps, company, director_scores)
              for k in claim_keys]

    # Build graph
    G = nx.DiGraph()
    thesis_id = "thesis::" + str(safe_get(primary_thesis, "name", "Thesis"))
    G.add_node(thesis_id, type="thesis",
               label=str(safe_get(primary_thesis, "name", "Thesis")),
               score=safe_float(safe_get(primary_thesis, "score", 50), 50))

    for c in claims:
        cid = "claim::" + c["claim_id"]
        G.add_node(cid, type="claim", label=c["claim_text"],
                   power=c["claim_power_score"],
                   evidence=c["evidence_strength"],
                   rebuttability=c["rebuttability"])
        G.add_edge(thesis_id, cid, relation="supports")

        # Evidence node
        eid = "evidence::" + c["claim_id"]
        G.add_node(eid, type="evidence", label=f"Evidence: {c['claim_text'][:60]}",
                   strength=c["evidence_strength"])
        G.add_edge(cid, eid, relation="evidenced_by")

        # Rebuttal node
        rid = "rebuttal::" + c["claim_id"]
        G.add_node(rid, type="rebuttal", label=f"Management rebuttal capacity",
                   strength=c["rebuttability"])
        G.add_edge(cid, rid, relation="rebutted_by")

        # Affected shareholder groups
        for g in _affected_shareholder_groups(c["claim_type"]):
            sid = "shareholders::" + g
            G.add_node(sid, type="shareholder_group", label=g)
            G.add_edge(cid, sid, relation="affects")

        # Exposed directors
        for d in _exposed_directors(c["claim_type"], director_scores):
            did = "director::" + str(d.get("director_id", "D000"))
            G.add_node(did, type="director", label=d.get("name", "Director"),
                       risk=d.get("score", 50))
            G.add_edge(cid, did, relation="implicates")

        # Recommended defenses
        for i, defn in enumerate(_recommended_defenses(c["claim_type"])):
            did_node = f"defense::{c['claim_id']}::{i}"
            G.add_node(did_node, type="defense", label=defn,
                       priority=c["defense_priority"])
            G.add_edge(cid, did_node, relation="defended_by")

    # Convert to node-link dict
    nl = json_graph.node_link_data(G, edges="links")

    strongest = sorted(claims, key=lambda c: c["claim_power_score"], reverse=True)[:3]
    most_rebut = sorted(claims, key=lambda c: c["rebuttability"], reverse=True)[:3]
    highest_priority = sorted(claims, key=lambda c: c["defense_priority"], reverse=True)[:3]

    summary = (
        f"Thesis decomposed into {len(claims)} claims. "
        f"Strongest claim: {strongest[0]['claim_text']} "
        f"(power {strongest[0]['claim_power_score']:.0f}/100). "
        f"Most rebuttable: {most_rebut[0]['claim_text']} "
        f"(rebuttability {most_rebut[0]['rebuttability']:.0f}/100)."
    ) if claims else "No claims could be generated."

    return {
        "graph": nl,
        "claims": claims,
        "strongest_claims": strongest,
        "most_rebuttable_claims": most_rebut,
        "highest_priority_defense_claims": highest_priority,
        "claim_summary": summary,
    }


def generate_claim_level_attack_table(claim_graph_result):
    """Activist-side view: claims sorted by attack power."""
    claims = list(claim_graph_result.get("claims", []))
    out = []
    for c in sorted(claims, key=lambda x: x["claim_power_score"], reverse=True):
        out.append({
            "claim": c["claim_text"],
            "claim_power": round(c["claim_power_score"], 1),
            "evidence_strength": round(c["evidence_strength"], 1),
            "shareholder_resonance": round(c["shareholder_resonance"], 1),
            "proxy_advisor_resonance": round(c["proxy_advisor_resonance"], 1),
            "rebuttability": round(c["rebuttability"], 1),
        })
    return out


def generate_claim_level_defense_table(claim_graph_result):
    """Defense-side view: claims sorted by defense priority."""
    claims = list(claim_graph_result.get("claims", []))
    out = []
    for c in sorted(claims, key=lambda x: x["defense_priority"], reverse=True):
        out.append({
            "claim": c["claim_text"],
            "defense_priority": round(c["defense_priority"], 1),
            "rebuttability": round(c["rebuttability"], 1),
            "board_accountability": round(c["board_accountability"], 1),
            "recommended_defenses": "; ".join(_recommended_defenses(c["claim_type"])),
        })
    return out
