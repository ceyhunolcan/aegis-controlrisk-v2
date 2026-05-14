# Small numeric helpers used by basically every scoring engine.
# Convention: scores are 0-100, probabilities are 0-1, vote shares are 0-100.
import math


def safe_float(value, default=50.0):
    if value is None:
        return float(default)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isnan(f) or math.isinf(f):
        return float(default)
    return f


def safe_get(d, key, default=None):
    if not isinstance(d, dict):
        return default
    v = d.get(key, default)
    return default if v is None else v


def clamp(value, low=0.0, high=100.0):
    v = safe_float(value, default=(low + high) / 2.0)
    if v < low: return float(low)
    if v > high: return float(high)
    return float(v)


def probability_clamp(p):
    return clamp(p, 0.0, 1.0)


def normalize_0_100(value, min_value, max_value, inverse=False):
    """Linear normalize into [0, 100]. inverse=True flips it."""
    v = safe_float(value, default=(min_value + max_value) / 2.0)
    if max_value == min_value:
        return 50.0
    pct = (v - min_value) / (max_value - min_value)
    pct = max(0.0, min(1.0, pct))
    if inverse:
        pct = 1.0 - pct
    return clamp(pct * 100.0)


def weighted_score(component_dict, weights_dict):
    """
    Weighted average of components with renormalization.
    Missing components default to 50 (neutral) so we don't silently shrink
    when a signal is unavailable.
    """
    if not weights_dict:
        return 50.0
    total_w = 0.0
    acc = 0.0
    for k, w in weights_dict.items():
        w = safe_float(w, default=0.0)
        if w <= 0:
            continue
        comp = component_dict.get(k) if isinstance(component_dict, dict) else None
        acc += clamp(safe_float(comp, default=50.0)) * w
        total_w += w
    if total_w <= 0:
        return 50.0
    return clamp(acc / total_w)


def safe_mean(values, default=50.0):
    if values is None:
        return float(default)
    nums = []
    for v in values:
        f = safe_float(v, default=math.nan)
        if not (math.isnan(f) or math.isinf(f)):
            nums.append(f)
    return sum(nums) / len(nums) if nums else float(default)


# pandas + csv readers give us all kinds of garbage for boolean columns
def coerce_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        # NaN check
        if isinstance(value, float) and math.isnan(value):
            return default
        return bool(value)
    s = str(value).strip().lower()
    if s in {"true", "t", "yes", "y", "1"}:
        return True
    if s in {"false", "f", "no", "n", "0", ""}:
        return False
    return default
