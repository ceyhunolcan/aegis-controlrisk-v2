# Snapshot persistence + content hashing. The use case: "we ran this on
# March 14, what did we conclude" - either for litigation, for diffing
# against a later run, or for showing a client the trajectory.
#
# Snapshots are stored as JSON files keyed by content hash. Each snapshot
# captures: the analysis dict (with everything that's serializable), the
# input data shape, the timestamp, the random seed, and a summary digest.
#
# We can't pickle the whole dict because networkx graphs round-trip via
# json_graph already, and we want diffs to be human-readable.
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


SNAPSHOT_DIR = Path("snapshots")


def _safe_for_json(obj):
    """Coerce numpy / pandas / unhashable types into JSON-safe equivalents."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_for_json(x) for x in obj]
    # numpy scalars
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except (ValueError, TypeError):
            pass
    # pandas Timestamp etc.
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass
    # last resort
    return str(obj)


def _content_hash(payload):
    """Stable hash of the snapshot payload. SHA-256, first 16 chars."""
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _summary_digest(analysis):
    """Tiny dict of the headline numbers - used for change detection."""
    final = analysis.get("final_score") or {}
    sim = analysis.get("simulation") or {}
    vuln = analysis.get("vulnerability") or {}
    return {
        "risk_level": final.get("final_risk_level"),
        "risk_score": final.get("activism_risk_score_0_100"),
        "p_event_12m": final.get("activism_event_probability_12m"),
        "p_activist_wins_1_plus": sim.get("p_activist_wins_1_plus"),
        "vulnerability": vuln.get("score"),
        "primary_thesis": (analysis.get("primary_thesis") or {}).get("name"),
    }


def save_snapshot(analysis, snapshot_dir=None, note=""):
    """
    Persist an analysis dict to disk. Returns the snapshot record metadata.

    Note can be anything: 'pre-Q3 earnings', 'post-13D filing', whatever the
    user wants to remember it as.
    """
    snapshot_dir = Path(snapshot_dir or SNAPSHOT_DIR)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    company_id = analysis.get("company_id") or "UNKNOWN"
    ts_utc = datetime.now(timezone.utc).isoformat()
    payload = _safe_for_json(analysis)

    h = _content_hash(payload)
    rec = {
        "snapshot_id": f"{company_id}_{h}",
        "company_id": company_id,
        "captured_at_utc": ts_utc,
        "captured_at_epoch": time.time(),
        "content_hash": h,
        "note": note,
        "summary": _summary_digest(analysis),
        "analysis": payload,
    }

    fname = f"{company_id}_{ts_utc.replace(':', '-')}_{h}.json"
    path = snapshot_dir / fname
    path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")

    # Strip the heavy payload from the return value; callers usually
    # only want the receipt
    receipt = {k: v for k, v in rec.items() if k != "analysis"}
    receipt["path"] = str(path)
    return receipt


def load_snapshot(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def list_snapshots(company_id=None, snapshot_dir=None):
    """List all snapshots, optionally filtered by company."""
    snapshot_dir = Path(snapshot_dir or SNAPSHOT_DIR)
    if not snapshot_dir.exists():
        return []
    results = []
    for p in sorted(snapshot_dir.glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if company_id and rec.get("company_id") != company_id:
            continue
        # don't ship the big analysis payload back
        results.append({
            "snapshot_id": rec.get("snapshot_id"),
            "company_id": rec.get("company_id"),
            "captured_at_utc": rec.get("captured_at_utc"),
            "content_hash": rec.get("content_hash"),
            "note": rec.get("note", ""),
            "summary": rec.get("summary") or {},
            "path": str(p),
        })
    return results


def diff_snapshots(snap_old, snap_new):
    """
    Walk two snapshots and surface what changed in the summary digest +
    risk level + the top-level scoring outputs.

    Returns a list of {field, old, new, delta} dicts. Numeric fields get a
    delta; categorical fields just get old/new.
    """
    a = snap_old.get("analysis") if "analysis" in snap_old else snap_old
    b = snap_new.get("analysis") if "analysis" in snap_new else snap_new

    changes = []
    fields = [
        ("final_score", "final_risk_level", False),
        ("final_score", "activism_risk_score_0_100", True),
        ("final_score", "activism_event_probability_12m", True),
        ("final_score", "control_loss_probability_if_attacked", True),
        ("final_score", "settlement_pressure_index", True),
        ("vulnerability", "score", True),
        ("fixability", "score", True),
        ("defense", "defense_strength_score", True),
        ("bank_opportunity", "mandate_opportunity_score", True),
        ("simulation", "p_activist_wins_1_plus", True),
        ("simulation", "p_proxy_vote", True),
        ("settlement", "recommended_path", False),
        ("primary_thesis", "name", False),
    ]
    for top, sub, numeric in fields:
        old_v = (a.get(top) or {}).get(sub)
        new_v = (b.get(top) or {}).get(sub)
        if old_v == new_v:
            continue
        rec = {"field": f"{top}.{sub}", "old": old_v, "new": new_v}
        if numeric:
            try:
                rec["delta"] = round(float(new_v) - float(old_v), 3)
            except (TypeError, ValueError):
                pass
        changes.append(rec)

    return {
        "n_changes": len(changes),
        "changes": changes,
        "captured_old": snap_old.get("captured_at_utc"),
        "captured_new": snap_new.get("captured_at_utc"),
    }
