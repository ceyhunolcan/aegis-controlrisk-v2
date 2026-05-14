# Workspaces - the multi-tenant primitive. A workspace owns:
#   - a name + owner
#   - a watchlist of company IDs
#   - per-user roles (owner / analyst / viewer)
#   - alert subscription preferences (severity threshold + channel)
#   - free-form notes per company
#
# Storage is JSON-on-disk for the MVP. The interface is what matters - swap
# in Postgres later without touching anything that imports this module.
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE_DIR = Path(".aegis_workspaces")


def _new_id():
    return uuid.uuid4().hex[:12]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _path_for(workspace_id, workspace_dir=None):
    workspace_dir = Path(workspace_dir or WORKSPACE_DIR)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir / f"{workspace_id}.json"


def create_workspace(name, owner_email, workspace_dir=None):
    ws = {
        "workspace_id": _new_id(),
        "name": name,
        "created_at_utc": _now(),
        "owner_email": owner_email,
        "members": [
            {"email": owner_email, "role": "owner",
             "added_at_utc": _now()},
        ],
        "watchlist": [],
        "company_notes": {},
        "alert_subscriptions": {
            # default: notify the owner on high or critical for any watched company
            owner_email: {
                "min_severity": "high",
                "channel": "email",
                "company_ids": [],  # empty = all watched
            },
        },
    }
    _save(ws, workspace_dir)
    return ws


def _save(ws, workspace_dir=None):
    ws["updated_at_utc"] = _now()
    _path_for(ws["workspace_id"], workspace_dir).write_text(
        json.dumps(ws, indent=2), encoding="utf-8"
    )


def load_workspace(workspace_id, workspace_dir=None):
    path = _path_for(workspace_id, workspace_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_workspaces(workspace_dir=None):
    workspace_dir = Path(workspace_dir or WORKSPACE_DIR)
    if not workspace_dir.exists():
        return []
    out = []
    for p in sorted(workspace_dir.glob("*.json")):
        try:
            ws = json.loads(p.read_text(encoding="utf-8"))
            out.append({
                "workspace_id": ws.get("workspace_id"),
                "name": ws.get("name"),
                "owner_email": ws.get("owner_email"),
                "n_watched": len(ws.get("watchlist", [])),
                "n_members": len(ws.get("members", [])),
            })
        except (OSError, json.JSONDecodeError):
            continue
    return out


# Member management ----------------------------------------------------

VALID_ROLES = {"owner", "analyst", "viewer"}


def add_member(workspace_id, email, role="analyst", workspace_dir=None):
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}")
    ws = load_workspace(workspace_id, workspace_dir)
    if not ws:
        raise KeyError(f"workspace {workspace_id} not found")
    # idempotent: don't duplicate
    for m in ws["members"]:
        if m["email"] == email:
            m["role"] = role
            _save(ws, workspace_dir)
            return ws
    ws["members"].append({"email": email, "role": role,
                          "added_at_utc": _now()})
    _save(ws, workspace_dir)
    return ws


def remove_member(workspace_id, email, workspace_dir=None):
    ws = load_workspace(workspace_id, workspace_dir)
    if not ws:
        raise KeyError(f"workspace {workspace_id} not found")
    if email == ws["owner_email"]:
        raise ValueError("can't remove the owner; transfer ownership first")
    ws["members"] = [m for m in ws["members"] if m["email"] != email]
    ws["alert_subscriptions"].pop(email, None)
    _save(ws, workspace_dir)
    return ws


def role_for(ws, email):
    for m in (ws or {}).get("members", []):
        if m["email"] == email:
            return m["role"]
    return None


def can_edit(ws, email):
    return role_for(ws, email) in ("owner", "analyst")


# Watchlist ------------------------------------------------------------

def add_to_watchlist(workspace_id, company_id, workspace_dir=None):
    ws = load_workspace(workspace_id, workspace_dir)
    if not ws:
        raise KeyError(f"workspace {workspace_id} not found")
    if company_id not in ws["watchlist"]:
        ws["watchlist"].append(company_id)
        _save(ws, workspace_dir)
    return ws


def remove_from_watchlist(workspace_id, company_id, workspace_dir=None):
    ws = load_workspace(workspace_id, workspace_dir)
    if not ws:
        raise KeyError(f"workspace {workspace_id} not found")
    ws["watchlist"] = [c for c in ws["watchlist"] if c != company_id]
    ws["company_notes"].pop(company_id, None)
    _save(ws, workspace_dir)
    return ws


# Notes ---------------------------------------------------------------

def add_note(workspace_id, company_id, author_email, text,
             workspace_dir=None):
    ws = load_workspace(workspace_id, workspace_dir)
    if not ws:
        raise KeyError(f"workspace {workspace_id} not found")
    if not can_edit(ws, author_email):
        raise PermissionError(f"{author_email} can't add notes "
                              f"(role: {role_for(ws, author_email)})")
    notes = ws["company_notes"].setdefault(company_id, [])
    notes.append({
        "note_id": _new_id(),
        "author_email": author_email,
        "text": text,
        "created_at_utc": _now(),
    })
    _save(ws, workspace_dir)
    return ws


# Alert subscriptions -------------------------------------------------

def set_alert_subscription(workspace_id, email, min_severity="high",
                            channel="email", company_ids=None,
                            workspace_dir=None):
    ws = load_workspace(workspace_id, workspace_dir)
    if not ws:
        raise KeyError(f"workspace {workspace_id} not found")
    ws["alert_subscriptions"][email] = {
        "min_severity": min_severity,
        "channel": channel,
        "company_ids": company_ids or [],
    }
    _save(ws, workspace_dir)
    return ws


def subscribers_for(ws, company_id, severity):
    """Return list of (email, channel) tuples that should receive an alert
    of `severity` on `company_id`."""
    order = {"info": 0, "moderate": 1, "high": 2, "critical": 3}
    target = order.get(severity, 0)
    out = []
    for email, sub in (ws or {}).get("alert_subscriptions", {}).items():
        if order.get(sub.get("min_severity"), 0) > target:
            continue
        # company_ids empty = all watched
        scope = sub.get("company_ids") or []
        if scope and company_id not in scope:
            continue
        out.append((email, sub.get("channel", "email")))
    return out
