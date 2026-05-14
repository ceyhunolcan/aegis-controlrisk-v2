from .normalization import clamp, safe_float


def calculate_confidence(data_completeness, signal_consistency, model_support, source_quality):
    """Blend four 0-100 drivers into a single confidence score + level."""
    dc = clamp(safe_float(data_completeness, 50))
    sc = clamp(safe_float(signal_consistency, 50))
    ms = clamp(safe_float(model_support, 50))
    sq = clamp(safe_float(source_quality, 50))

    score = clamp(0.30 * dc + 0.25 * sc + 0.25 * ms + 0.20 * sq)

    if score >= 70:
        level = "High"
    elif score >= 45:
        level = "Moderate"
    else:
        level = "Low"

    return {
        "confidence_score": score,
        "confidence_level": level,
        "drivers": [
            f"Data completeness: {dc:.0f}/100",
            f"Signal consistency: {sc:.0f}/100",
            f"Model support: {ms:.0f}/100",
            f"Source quality: {sq:.0f}/100",
        ],
    }
