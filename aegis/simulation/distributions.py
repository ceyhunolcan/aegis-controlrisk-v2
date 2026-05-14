# Full distribution visualization for Monte Carlo outputs. Instead of
# reporting "P(activist wins ≥1 seat) = 0.62", show the full posterior
# distribution: what's the 5th percentile, what's the 95th, what's the
# shape of the uncertainty.
#
# Most activism tools report point estimates. This is the only thing in
# the market (as far as we know) that exposes the full distribution to
# decision-makers. Bankers and board attorneys care a lot about
# "what's the worst-plausible case" - the 95th percentile of seat loss,
# not the mean.
#
# Output format: a dict of distribution summaries suitable for the
# dashboard to render as histograms / fan charts.
import numpy as np


def distribution_summary(samples, percentiles=(5, 25, 50, 75, 95)):
    """Given a list/array of MC samples, return summary stats.

    Returns dict with:
        n, mean, std, min, max,
        p05, p25, p50, p75, p95 (configurable)
    """
    if samples is None or len(samples) == 0:
        return {
            "n": 0, "mean": None, "std": None, "min": None, "max": None,
            "percentiles": {},
        }
    arr = np.asarray(samples, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return {
            "n": 0, "mean": None, "std": None, "min": None, "max": None,
            "percentiles": {},
        }
    pcts = {f"p{p:02d}": float(np.percentile(arr, p)) for p in percentiles}
    return {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "percentiles": pcts,
    }


def histogram_bins(samples, n_bins=20):
    """Compute histogram bins for plotting.

    Returns dict with `edges` (bin boundaries) and `counts` (bin counts).
    """
    if samples is None or len(samples) == 0:
        return {"edges": [], "counts": []}
    arr = np.asarray(samples, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return {"edges": [], "counts": []}
    counts, edges = np.histogram(arr, bins=n_bins)
    return {
        "edges": [float(e) for e in edges],
        "counts": [int(c) for c in counts],
    }


def credible_interval(samples, alpha=0.10):
    """Return the (alpha/2, 1-alpha/2) credible interval.

    Default 90% credible interval (alpha=0.10 -> [5th, 95th]).
    """
    if samples is None or len(samples) == 0:
        return None, None
    arr = np.asarray(samples, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return None, None
    lo = float(np.percentile(arr, 100 * (alpha / 2)))
    hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
    return lo, hi


def fan_chart_data(samples_by_scenario):
    """Build fan-chart data from a dict of {scenario_name: samples}.

    Returns a list of dicts suitable for plotly/altair, each with the
    p05/p25/p50/p75/p95 of one scenario.
    """
    rows = []
    for name, samples in samples_by_scenario.items():
        s = distribution_summary(samples)
        rows.append({
            "scenario": name,
            "mean": s["mean"],
            **s["percentiles"],
        })
    return rows


def worst_case_summary(samples_seats_lost, p_threshold=95):
    """Given an array of "seats lost" samples from MC, summarize the
    worst-case story.

    Returns dict with:
        mean_seats_lost, p95_seats_lost, p_lose_at_least_1,
        p_lose_at_least_2, p_lose_at_least_3,
        worst_case_message (string fit for a board memo)
    """
    if samples_seats_lost is None or len(samples_seats_lost) == 0:
        return None
    arr = np.asarray(samples_seats_lost, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return None

    mean = float(np.mean(arr))
    p95 = float(np.percentile(arr, p_threshold))
    p_1plus = float(np.mean(arr >= 1))
    p_2plus = float(np.mean(arr >= 2))
    p_3plus = float(np.mean(arr >= 3))

    if p95 >= 3:
        worst = (f"Worst-plausible case ({p_threshold}th percentile): "
                 f"loss of {p95:.0f}+ board seats. Treat as "
                 f"control-loss-adjacent.")
    elif p95 >= 2:
        worst = (f"Worst-plausible case ({p_threshold}th percentile): "
                 f"loss of 2 seats. Plan for shared governance.")
    elif p95 >= 1:
        worst = (f"Worst-plausible case ({p_threshold}th percentile): "
                 f"loss of 1 seat. Settlement likely.")
    else:
        worst = (f"Worst-plausible case ({p_threshold}th percentile): "
                 f"no seat loss. Defense scenario is dominant.")

    return {
        "mean_seats_lost": round(mean, 2),
        "p95_seats_lost": round(p95, 1),
        "p_lose_at_least_1": round(p_1plus, 3),
        "p_lose_at_least_2": round(p_2plus, 3),
        "p_lose_at_least_3": round(p_3plus, 3),
        "worst_case_message": worst,
    }
