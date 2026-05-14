# Disk-backed pipeline cache. The pipeline takes ~150ms per company on
# this dataset and produces a ~50KB JSON payload. For the dashboard we
# already cache via st.cache_data. For batch jobs, CLI use, and re-running
# the memo writer without recomputing scores, we want a persistent cache.
#
# Keying: company_id + as_of_date + data_hash + model_version. Anything
# that should bust the cache goes into the key.
import hashlib
import json
import time
from pathlib import Path

from .. import __version__ as MODEL_VERSION


CACHE_DIR = Path(".aegis_cache")


def _data_fingerprint(data):
    """Quick fingerprint of the input data dict. Just shape + first row hash
    of each table - we're not trying to detect every cell change, we're
    trying to detect 'is this the same data load'."""
    parts = []
    for key in sorted(data.keys()):
        df = data[key]
        if df is None:
            parts.append(f"{key}:none")
            continue
        try:
            n = len(df)
            cols = ",".join(map(str, df.columns)) if hasattr(df, "columns") else ""
            parts.append(f"{key}:{n}:{cols}")
        except Exception:
            parts.append(f"{key}:?")
    blob = "|".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def _cache_key(company_id, as_of_date, data, model_version=None):
    fp = _data_fingerprint(data)
    mv = model_version or MODEL_VERSION
    date_str = str(as_of_date) if as_of_date else "today"
    raw = f"{company_id}|{date_str}|{fp}|{mv}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def get(company_id, data, as_of_date=None, cache_dir=None,
        max_age_sec=86400):
    """Return cached analysis dict, or None if absent/stale."""
    cache_dir = Path(cache_dir or CACHE_DIR)
    if not cache_dir.exists():
        return None
    key = _cache_key(company_id, as_of_date, data)
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    age = time.time() - rec.get("cached_at_epoch", 0)
    if max_age_sec is not None and age > max_age_sec:
        return None
    return rec.get("analysis")


def put(company_id, analysis, data, as_of_date=None, cache_dir=None):
    """Persist an analysis dict to the cache."""
    cache_dir = Path(cache_dir or CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(company_id, as_of_date, data)
    path = cache_dir / f"{key}.json"
    rec = {
        "key": key,
        "company_id": company_id,
        "cached_at_epoch": time.time(),
        "analysis": _make_json_safe(analysis),
    }
    path.write_text(json.dumps(rec, default=str), encoding="utf-8")
    return str(path)


def _make_json_safe(obj):
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(x) for x in obj]
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except (ValueError, TypeError):
            pass
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return str(obj)


def clear(cache_dir=None):
    """Wipe the cache. Useful when bumping model version manually."""
    cache_dir = Path(cache_dir or CACHE_DIR)
    if not cache_dir.exists():
        return 0
    n = 0
    for p in cache_dir.glob("*.json"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n


def stats(cache_dir=None):
    """How many entries, total disk bytes, oldest/newest timestamp."""
    cache_dir = Path(cache_dir or CACHE_DIR)
    if not cache_dir.exists():
        return {"n_entries": 0, "total_bytes": 0}
    entries = list(cache_dir.glob("*.json"))
    if not entries:
        return {"n_entries": 0, "total_bytes": 0}
    sizes = [p.stat().st_size for p in entries]
    times = []
    for p in entries:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            times.append(rec.get("cached_at_epoch", 0))
        except Exception:
            pass
    return {
        "n_entries": len(entries),
        "total_bytes": sum(sizes),
        "oldest_epoch": min(times) if times else None,
        "newest_epoch": max(times) if times else None,
    }
