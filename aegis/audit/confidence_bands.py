# Confidence bands for MC outputs. The pipeline runs N=10000 simulations
# and reports a point estimate. We also want to know how tight that estimate
# is - is the 95% CI [0.62, 0.66] or [0.40, 0.85]?
#
# Bootstrap on the simulation outcomes. Cheap because we already have the
# samples, we're just resampling them.
import numpy as np


def bootstrap_ci(samples, statistic_fn, n_bootstrap=1000, alpha=0.05,
                 random_seed=42):
    """
    Bootstrap CI for any statistic on `samples`.

    statistic_fn: callable that takes an array and returns a scalar (e.g.
        np.mean for the mean, or a lambda for "fraction of samples in
        category X").

    Returns dict with point estimate, lo, hi, std.
    """
    if samples is None or len(samples) == 0:
        return {"point": None, "lo": None, "hi": None, "std": None,
                "n_bootstrap": 0}

    arr = np.asarray(samples)
    rng = np.random.default_rng(random_seed)
    n = len(arr)

    point = float(statistic_fn(arr))
    boot_stats = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        boot_stats[i] = statistic_fn(arr[idx])

    lo = float(np.quantile(boot_stats, alpha / 2.0))
    hi = float(np.quantile(boot_stats, 1.0 - alpha / 2.0))
    return {
        "point": round(point, 4),
        "lo": round(lo, 4),
        "hi": round(hi, 4),
        "std": round(float(np.std(boot_stats)), 4),
        "n_bootstrap": n_bootstrap,
        "alpha": alpha,
    }


def confidence_bands_for_simulation(simulation_result, n_bootstrap=500):
    """
    Compute bootstrap CIs for the key MC probability outputs.

    The MC results include per-simulation outcomes; we resample those.
    If only summary stats are present (no raw outcomes), we fall back to
    a normal approximation using the sample size.
    """
    if not simulation_result:
        return {}

    # If raw per-sim outcomes are available, real bootstrap
    raw_outcomes = simulation_result.get("raw_outcomes")
    n_sims = simulation_result.get("n_simulations", 10000)

    out = {}
    for key in ("p_activist_wins_1_plus", "p_activist_wins_2_plus",
                "p_activist_wins_3_plus", "p_proxy_vote",
                "p_private_settlement", "p_company_full_defense",
                "p_strategic_review"):
        p = simulation_result.get(key)
        if p is None:
            continue
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        # Normal approx for binomial proportion - cheap and good enough
        # for n=10000 sims
        se = np.sqrt(p * (1 - p) / max(n_sims, 1))
        out[key] = {
            "point": round(p, 4),
            "lo": round(max(0.0, p - 1.96 * se), 4),
            "hi": round(min(1.0, p + 1.96 * se), 4),
            "std": round(float(se), 4),
            "method": "normal_approx",
            "n_simulations": n_sims,
        }

    return out


def data_freshness_score(data_sources_with_timestamps):
    """
    Given a list of (source_name, timestamp_iso) tuples, return a 0-100
    freshness score plus warnings for anything older than 30 days.

    100 = today, 0 = >90 days old.
    """
    from datetime import datetime, timezone, timedelta

    if not data_sources_with_timestamps:
        return {"score": None, "warnings": ["no data sources tracked"]}

    now = datetime.now(timezone.utc)
    ages = []
    warnings = []

    for source, ts in data_sources_with_timestamps:
        if not ts:
            warnings.append(f"{source}: no timestamp")
            continue
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                dt = ts
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = (now - dt).total_seconds() / 86400.0
            ages.append(age_days)
            if age_days > 30:
                warnings.append(f"{source}: {age_days:.0f} days old")
        except (ValueError, TypeError):
            warnings.append(f"{source}: bad timestamp {ts}")

    if not ages:
        return {"score": None, "warnings": warnings}

    median_age = sorted(ages)[len(ages) // 2]
    # 0 days -> 100, 90+ days -> 0, linear in between
    score = max(0.0, 100.0 - (median_age / 90.0) * 100.0)
    return {
        "score": round(score, 1),
        "median_age_days": round(median_age, 1),
        "max_age_days": round(max(ages), 1),
        "warnings": warnings,
    }
