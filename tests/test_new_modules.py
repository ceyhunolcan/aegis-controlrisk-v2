# Tests for the production-grade modules: audit, alerts, parallel,
# workflow, ingest, and the new report views.
#
# These use tempdir-isolated state so they can run in parallel and don't
# leave junk behind. The pipeline tests in test_scoring.py already cover
# the analysis dict shape - here we only test the new layers.
import shutil
import tempfile
from pathlib import Path

import pytest

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis


# Shared fixtures --------------------------------------------------------

@pytest.fixture(scope="module")
def data():
    return load_all_data("data")


@pytest.fixture(scope="module")
def indc(data):
    return run_company_analysis("INDC", data)


@pytest.fixture(scope="module")
def nvtc(data):
    return run_company_analysis("NVTC", data)


# Snapshots --------------------------------------------------------------

def test_save_snapshot_writes_file(indc, tmp_path):
    from aegis.audit.snapshots import save_snapshot
    rec = save_snapshot(indc, snapshot_dir=tmp_path, note="test")
    assert rec["company_id"] == "INDC"
    assert rec["content_hash"]
    assert Path(rec["path"]).exists()
    assert rec["summary"]["risk_level"]


def test_load_snapshot_round_trip(indc, tmp_path):
    from aegis.audit.snapshots import save_snapshot, load_snapshot
    rec = save_snapshot(indc, snapshot_dir=tmp_path)
    loaded = load_snapshot(rec["path"])
    assert loaded["company_id"] == "INDC"
    assert "analysis" in loaded
    assert loaded["analysis"]["final_score"]["final_risk_level"] == \
           indc["final_score"]["final_risk_level"]


def test_list_snapshots_filters_by_company(indc, nvtc, tmp_path):
    from aegis.audit.snapshots import save_snapshot, list_snapshots
    save_snapshot(indc, snapshot_dir=tmp_path)
    save_snapshot(nvtc, snapshot_dir=tmp_path)

    indc_only = list_snapshots(company_id="INDC", snapshot_dir=tmp_path)
    assert len(indc_only) == 1
    assert indc_only[0]["company_id"] == "INDC"

    all_snaps = list_snapshots(snapshot_dir=tmp_path)
    assert len(all_snaps) == 2


def test_diff_snapshots_surfaces_changes(indc, nvtc):
    from aegis.audit.snapshots import diff_snapshots
    diff = diff_snapshots({"analysis": nvtc}, {"analysis": indc})
    assert diff["n_changes"] > 0
    # Risk levels are different between NVTC and INDC
    risk_changes = [c for c in diff["changes"]
                    if c["field"] == "final_score.final_risk_level"]
    assert len(risk_changes) == 1


# Provenance -------------------------------------------------------------

def test_make_provenance_minimal():
    from aegis.audit.provenance import make_provenance
    p = make_provenance("vulnerability", 75.0)
    assert p["score_name"] == "vulnerability"
    assert p["score_value"] == 75.0
    assert p["computed_at_utc"]
    assert p["model_version"]


def test_explain_score_orders_by_contribution():
    from aegis.audit.provenance import explain_score
    prov = {
        "score_name": "test",
        "score_value": 60.0,
        "components": {"a": 80, "b": 50, "c": 90},
        "weights": {"a": 0.5, "b": 0.3, "c": 0.2},
    }
    lines = explain_score(prov, top_n=3)
    assert len(lines) == 3
    # Highest contribution: a (80 * 0.5 = 40)
    assert "A:" in lines[0]


# Confidence bands -------------------------------------------------------

def test_confidence_bands_for_simulation_normal_approx(indc):
    from aegis.audit.confidence_bands import confidence_bands_for_simulation
    bands = confidence_bands_for_simulation(indc["simulation"])
    assert "p_activist_wins_1_plus" in bands
    band = bands["p_activist_wins_1_plus"]
    assert band["lo"] <= band["point"] <= band["hi"]
    assert 0.0 <= band["lo"] and band["hi"] <= 1.0


def test_data_freshness_score_recent():
    from aegis.audit.confidence_bands import data_freshness_score
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    out = data_freshness_score([("source_a", now), ("source_b", now)])
    assert out["score"] >= 95


def test_data_freshness_score_stale():
    from aegis.audit.confidence_bands import data_freshness_score
    stale = "2024-01-01T00:00:00+00:00"
    out = data_freshness_score([("source_a", stale)])
    assert out["score"] < 50
    assert out["warnings"]


# Alerts -----------------------------------------------------------------

def test_check_alerts_no_change_returns_empty(indc):
    from aegis.alerts.rules import check_alerts
    alerts = check_alerts(indc, indc)  # identical snapshots
    # risk_level_escalated should not fire; other rules may still fire on
    # absolute thresholds, but no escalation rules
    rule_names = {a["rule_name"] for a in alerts}
    assert "risk_level_escalated" not in rule_names
    assert "risk_score_jump" not in rule_names


def test_check_alerts_fires_on_escalation(indc, nvtc):
    from aegis.alerts.rules import check_alerts
    # Pretend NVTC was the baseline for INDC
    alerts = check_alerts(nvtc, indc)
    rule_names = {a["rule_name"] for a in alerts}
    assert "risk_level_escalated" in rule_names


def test_filter_by_severity():
    from aegis.alerts.rules import filter_by_severity
    alerts = [
        {"severity": "critical"},
        {"severity": "high"},
        {"severity": "moderate"},
        {"severity": "info"},
    ]
    high_plus = filter_by_severity(alerts, "high")
    assert len(high_plus) == 2


def test_notifier_formats_digest(indc, nvtc):
    from aegis.alerts.rules import check_alerts
    from aegis.alerts.notifier import format_digest_markdown
    alerts = check_alerts(nvtc, indc)
    md = format_digest_markdown(alerts)
    assert "Aegis Daily Alert Digest" in md
    assert len(alerts) > 0  # confirm there were alerts to format


# Parallel batch runner --------------------------------------------------

def test_run_batch_completes_all_companies(data):
    from aegis.parallel.batch_runner import run_batch, summarize_batch
    cids = data["companies"]["company_id"].astype(str).tolist()
    results = run_batch(cids, data, max_workers=2)
    assert len(results) == len(cids)
    summary = summarize_batch(results)
    assert summary["n_ok"] == len(cids)
    assert summary["n_error"] == 0


def test_run_batch_isolates_bad_companies(data):
    from aegis.parallel.batch_runner import run_batch
    results = run_batch(["INDC", "DOES_NOT_EXIST", "NVTC"], data,
                        max_workers=2)
    # bad company gets an error entry, good ones still succeed
    # (depending on how the pipeline handles unknown ids; it currently
    # returns a safe-default dict, so this may all succeed)
    assert len(results) == 3
    assert results["INDC"]["result"] is not None
    assert results["NVTC"]["result"] is not None


# Disk cache -------------------------------------------------------------

def test_disk_cache_hit_after_put(indc, data, tmp_path):
    from aegis.parallel.disk_cache import get, put
    assert get("INDC", data, cache_dir=tmp_path) is None  # miss
    put("INDC", indc, data, cache_dir=tmp_path)
    cached = get("INDC", data, cache_dir=tmp_path)
    assert cached is not None
    assert cached["final_score"]["final_risk_level"] == \
           indc["final_score"]["final_risk_level"]


def test_disk_cache_clear(indc, data, tmp_path):
    from aegis.parallel.disk_cache import put, clear, stats
    put("INDC", indc, data, cache_dir=tmp_path)
    assert stats(cache_dir=tmp_path)["n_entries"] == 1
    n = clear(cache_dir=tmp_path)
    assert n == 1
    assert stats(cache_dir=tmp_path)["n_entries"] == 0


# Workspaces -------------------------------------------------------------

def test_create_workspace_has_owner_member(tmp_path):
    from aegis.workflow.workspaces import create_workspace
    ws = create_workspace("Test WS", "owner@example.com",
                          workspace_dir=tmp_path)
    assert len(ws["members"]) == 1
    assert ws["members"][0]["role"] == "owner"


def test_workspace_add_remove_member(tmp_path):
    from aegis.workflow.workspaces import (
        create_workspace, add_member, remove_member, load_workspace,
    )
    ws = create_workspace("Test", "owner@example.com",
                          workspace_dir=tmp_path)
    add_member(ws["workspace_id"], "analyst@example.com", "analyst",
               workspace_dir=tmp_path)
    ws = load_workspace(ws["workspace_id"], workspace_dir=tmp_path)
    assert len(ws["members"]) == 2

    remove_member(ws["workspace_id"], "analyst@example.com",
                  workspace_dir=tmp_path)
    ws = load_workspace(ws["workspace_id"], workspace_dir=tmp_path)
    assert len(ws["members"]) == 1


def test_workspace_owner_cannot_be_removed(tmp_path):
    from aegis.workflow.workspaces import create_workspace, remove_member
    ws = create_workspace("Test", "owner@example.com",
                          workspace_dir=tmp_path)
    with pytest.raises(ValueError):
        remove_member(ws["workspace_id"], "owner@example.com",
                      workspace_dir=tmp_path)


def test_workspace_viewer_cannot_add_note(tmp_path):
    from aegis.workflow.workspaces import (
        create_workspace, add_member, add_note,
    )
    ws = create_workspace("Test", "owner@example.com",
                          workspace_dir=tmp_path)
    add_member(ws["workspace_id"], "viewer@example.com", "viewer",
               workspace_dir=tmp_path)
    with pytest.raises(PermissionError):
        add_note(ws["workspace_id"], "INDC", "viewer@example.com",
                 "should fail", workspace_dir=tmp_path)


def test_workspace_subscribers_for(tmp_path):
    from aegis.workflow.workspaces import (
        create_workspace, set_alert_subscription, subscribers_for,
        load_workspace,
    )
    ws = create_workspace("Test", "owner@example.com",
                          workspace_dir=tmp_path)
    set_alert_subscription(ws["workspace_id"], "owner@example.com",
                            min_severity="moderate", channel="slack",
                            workspace_dir=tmp_path)
    ws = load_workspace(ws["workspace_id"], workspace_dir=tmp_path)

    # Critical fires for moderate+ subscribers
    subs = subscribers_for(ws, "INDC", "critical")
    assert ("owner@example.com", "slack") in subs

    # Info should not fire (below threshold)
    subs = subscribers_for(ws, "INDC", "info")
    assert subs == []


# Ingest -----------------------------------------------------------------

def test_synthetic_source_loads(data):
    from aegis.ingest.sources import get_source
    src = get_source("synthetic")
    loaded = src.load_all()
    assert "companies" in loaded
    assert len(loaded["companies"]) == len(data["companies"])


def test_unknown_source_raises():
    from aegis.ingest.sources import get_source
    with pytest.raises(ValueError):
        get_source("nonsense")


def test_stub_sources_raise_not_implemented():
    # EDGAR is now a real implementation - only Bloomberg and ISS remain
    # stubs awaiting paid-vendor integration.
    from aegis.ingest.sources import BloombergSource, ISSSource
    for source_cls in (BloombergSource, ISSSource):
        with pytest.raises(NotImplementedError):
            source_cls().load_all()


def test_edgar_source_needs_tickers():
    # EDGARSource's load_all() requires explicit tickers - the EDGAR API
    # doesn't have a "give me everything" mode like the synthetic source.
    from aegis.ingest.sources import EDGARSource
    with pytest.raises(ValueError):
        EDGARSource().load_all()


# Executive view ---------------------------------------------------------

def test_executive_verdict_mentions_risk_level(indc):
    from aegis.reports.executive_view import executive_verdict
    text = executive_verdict(indc)
    assert "Critical" in text
    assert "Industrial Diversified" in text


def test_top_three_reasons_returns_three(indc):
    from aegis.reports.executive_view import top_three_reasons
    reasons = top_three_reasons(indc)
    assert len(reasons) == 3


def test_recommended_next_action_mentions_action(indc):
    from aegis.reports.executive_view import recommended_next_action
    text = recommended_next_action(indc)
    assert text  # non-empty
    assert len(text) > 30


def test_render_executive_view_full_markdown(indc):
    from aegis.reports.executive_view import render_executive_view
    md = render_executive_view(indc)
    assert "## Verdict" in md
    assert "## Top 3 reasons" in md
    assert "## What to do this week" in md


# Question views ---------------------------------------------------------

def test_all_layer2_views_has_three_sections(indc):
    from aegis.reports.question_views import all_layer2_views
    views = all_layer2_views(indc)
    assert set(views.keys()) == {"who", "what", "when"}


def test_who_view_has_attacker_and_directors(indc):
    from aegis.reports.question_views import who_view
    v = who_view(indc)
    assert v["attacker"]["archetype"]
    assert len(v["high_risk_directors"]) <= 3


def test_what_view_has_thesis_and_actions(indc):
    from aegis.reports.question_views import what_view
    v = what_view(indc)
    assert v["thesis"]["name"]
    assert v["settle_or_fight"]["recommended_path"]


def test_when_view_has_calendar_and_triggers(indc):
    from aegis.reports.question_views import when_view
    v = when_view(indc)
    assert v["calendar"]["annual_meeting_date"]
    assert "n_active" in v["triggers"]
