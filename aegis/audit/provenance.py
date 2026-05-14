# Provenance tracking. Given a score and the inputs that produced it,
# build a structured record of "here's where this number came from".
# This is what makes the difference between a black box and something
# a board attorney will sign off on.
#
# The provenance record is intentionally separate from the analysis dict
# itself - we don't want to bloat the main output. Callers opt in.
from datetime import datetime, timezone


def make_provenance(score_name, score_value, components=None,
                    weights=None, inputs=None, data_sources=None,
                    notes=None, model_version="2.0.0"):
    """
    Build a single provenance record. Everything is optional except the
    score name + value.

    components: dict of sub-component name -> value
    weights: dict of sub-component name -> weight (must align with components)
    inputs: dict of raw input field -> value (the financial data, etc.)
    data_sources: list of (field, source) pairs - e.g. ('tsr_3y', 'EDGAR')
    notes: free-form list of strings explaining edge cases / overrides
    """
    return {
        "score_name": score_name,
        "score_value": score_value,
        "components": components or {},
        "weights": weights or {},
        "inputs": inputs or {},
        "data_sources": data_sources or [],
        "notes": notes or [],
        "model_version": model_version,
        "computed_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def explain_score(provenance, top_n=5):
    """
    Turn a provenance record into a human-readable explanation, in order
    of contribution. Returns a list of one-line strings.
    """
    if not provenance:
        return []

    components = provenance.get("components", {}) or {}
    weights = provenance.get("weights", {}) or {}

    if not components:
        return [f"{provenance.get('score_name', 'score')} = "
                f"{provenance.get('score_value', '?')} (no component breakdown)"]

    # weighted contribution = component_value * weight
    contributions = []
    for name, val in components.items():
        try:
            v = float(val or 0)
            w = float(weights.get(name, 0) or 0)
            contributions.append((name, v, w, v * w))
        except (TypeError, ValueError):
            continue
    contributions.sort(key=lambda x: -abs(x[3]))

    lines = []
    for name, val, w, contrib in contributions[:top_n]:
        pretty = name.replace("_", " ").title()
        lines.append(
            f"{pretty}: {val:.1f}/100 × weight {w:.2f} = "
            f"{contrib:.1f} contribution"
        )
    return lines


def trace_to_inputs(provenance):
    """
    Given a provenance record, return a flat list of (input_field, value,
    source) tuples - the actual data that fed the score.
    """
    inputs = provenance.get("inputs", {}) or {}
    sources = dict(provenance.get("data_sources", []) or [])
    return [
        (field, value, sources.get(field, "synthetic"))
        for field, value in inputs.items()
    ]


def attach_provenance(analysis, score_name, provenance):
    """
    Hang a provenance record off the analysis dict under a _provenance key.
    Non-destructive - the main score stays where it is.
    """
    if "_provenance" not in analysis:
        analysis["_provenance"] = {}
    analysis["_provenance"][score_name] = provenance
    return analysis
