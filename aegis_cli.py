# Aegis CLI. The dashboard is great for browsing, but for cron jobs, CI
# pipelines, or scripted workflows you want a plain command-line tool.
#
# Aegis ControlRisk OS — Copyright (c) 2026. All rights reserved.
# Source-available under a proprietary license. See LICENSE / COMMERCIAL.md.
#
# Usage:
#   python aegis_cli.py analyze INDC                  # run one
#   python aegis_cli.py analyze INDC --json           # JSON output
#   python aegis_cli.py batch --workers 4             # run universe
#   python aegis_cli.py snapshot save INDC --note "Q3 close"
#   python aegis_cli.py snapshot list
#   python aegis_cli.py snapshot list --company INDC
#   python aegis_cli.py snapshot diff <id_old> <id_new>
#   python aegis_cli.py alerts --since-last-snapshot INDC
#
# Exit codes: 0 success, 1 user error, 2 internal error.
import argparse
import json
import sys

from aegis.data.loader import load_all_data
from aegis.pipeline import run_company_analysis


def _print_human_summary(analysis):
    """Compact text summary for terminal output."""
    company = analysis.get("company") or {}
    final = analysis.get("final_score") or {}
    sim = analysis.get("simulation") or {}
    vuln = analysis.get("vulnerability") or {}
    primary = analysis.get("primary_thesis") or {}
    settlement = analysis.get("settlement") or {}
    legal = analysis.get("legal") or {}

    name = company.get("name", "—")
    ticker = company.get("ticker", "—")
    print(f"\n{'=' * 70}")
    print(f" {name} ({ticker})")
    print(f"{'=' * 70}")
    print(f" Risk level:       {final.get('final_risk_level', '—')}")
    print(f" Composite score:  "
          f"{final.get('activism_risk_score_0_100', 0):.0f} / 100")
    print(f" P(activism 12m):  "
          f"{float(final.get('activism_event_probability_12m') or 0):.0%}")
    print(f" P(activist ≥1 seat in proxy):  "
          f"{float(sim.get('p_activist_wins_1_plus') or 0):.0%}")
    print(f" Vulnerability:    {vuln.get('score', '–'):.0f} ({vuln.get('level','—')})")
    print(f" Primary thesis:   {primary.get('name', '—')}")
    print(f" Recommended path: {settlement.get('recommended_path', '—')}")
    print(f" Annual meeting in: {legal.get('days_to_annual_meeting', '–')} days")
    print(f" Nomination deadline in: "
          f"{legal.get('days_to_nomination_deadline', '–')} days")
    print()


def cmd_analyze(args):
    data = load_all_data(args.data_dir)
    try:
        result = run_company_analysis(args.company_id, data)
    except Exception as e:
        print(f"Analysis failed: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        _print_human_summary(result)
    return 0


def cmd_batch(args):
    from aegis.parallel.batch_runner import run_universe, summarize_batch

    data = load_all_data(args.data_dir)
    print(f"Running pipeline for {len(data['companies'])} companies "
          f"(workers={args.workers})...")

    def _progress(completed, total, cid):
        print(f"  [{completed}/{total}] {cid}")

    results = run_universe(data, max_workers=args.workers)
    summary = summarize_batch(results)
    print(f"\nDone: {summary['n_ok']} ok / {summary['n_error']} error")
    print(f"Mean runtime: {summary['runtime_mean_sec']}s, "
          f"max: {summary['runtime_max_sec']}s")
    if summary["errors"]:
        print("Errors:")
        for cid, err in summary["errors"].items():
            print(f"  {cid}: {err}")

    if args.json:
        # Strip the heavy `result` field for json output
        compact = {
            cid: {
                "ok": v["result"] is not None,
                "error": v["error"],
                "risk_level": ((v["result"] or {}).get("final_score") or {})
                                .get("final_risk_level"),
                "risk_score": ((v["result"] or {}).get("final_score") or {})
                                .get("activism_risk_score_0_100"),
            }
            for cid, v in results.items()
        }
        print(json.dumps(compact, indent=2, default=str))
    return 0 if summary["n_error"] == 0 else 1


def cmd_snapshot_save(args):
    from aegis.audit.snapshots import save_snapshot

    data = load_all_data(args.data_dir)
    result = run_company_analysis(args.company_id, data)
    rec = save_snapshot(result, note=args.note or "")
    print(f"Saved snapshot {rec['snapshot_id']}")
    print(f"  path:        {rec['path']}")
    print(f"  hash:        {rec['content_hash']}")
    print(f"  risk_level:  {rec['summary']['risk_level']}")
    return 0


def cmd_snapshot_list(args):
    from aegis.audit.snapshots import list_snapshots
    snaps = list_snapshots(company_id=args.company)
    if not snaps:
        print("(no snapshots)")
        return 0
    print(f"{'snapshot_id':<28} {'company':<8} {'risk':<10} {'captured (UTC)'}")
    print("-" * 80)
    for s in snaps:
        print(f"{s['snapshot_id']:<28} "
              f"{s['company_id']:<8} "
              f"{(s['summary'].get('risk_level') or '—'):<10} "
              f"{s['captured_at_utc']}")
    return 0


def cmd_snapshot_diff(args):
    from aegis.audit.snapshots import list_snapshots, load_snapshot, diff_snapshots
    snaps = list_snapshots()
    by_id = {s["snapshot_id"]: s for s in snaps}
    if args.id_old not in by_id:
        print(f"Snapshot not found: {args.id_old}", file=sys.stderr)
        return 1
    if args.id_new not in by_id:
        print(f"Snapshot not found: {args.id_new}", file=sys.stderr)
        return 1
    a = load_snapshot(by_id[args.id_old]["path"])
    b = load_snapshot(by_id[args.id_new]["path"])
    diff = diff_snapshots(a, b)

    if args.json:
        print(json.dumps(diff, indent=2, default=str))
        return 0

    print(f"\n{diff['n_changes']} change(s) between snapshots:")
    print(f"  old: {diff.get('captured_old')}")
    print(f"  new: {diff.get('captured_new')}")
    print()
    for c in diff["changes"]:
        line = f"  {c['field']}: {c['old']} -> {c['new']}"
        if "delta" in c:
            line += f"  ({c['delta']:+.3f})"
        print(line)
    return 0


def cmd_alerts(args):
    from aegis.audit.snapshots import list_snapshots, load_snapshot
    from aegis.alerts.rules import check_alerts, filter_by_severity
    from aegis.alerts.notifier import format_email_text

    data = load_all_data(args.data_dir)
    current = run_company_analysis(args.company_id, data)

    snaps = [s for s in list_snapshots(company_id=args.company_id)]
    if not snaps:
        print(f"No prior snapshot for {args.company_id}. "
              f"Run `snapshot save {args.company_id}` first.",
              file=sys.stderr)
        return 1
    prior = load_snapshot(snaps[-1]["path"]).get("analysis")
    alerts = check_alerts(prior, current)
    alerts = filter_by_severity(alerts, args.min_severity)

    if not alerts:
        print("(no alerts at this severity or above)")
        return 0

    print(format_email_text(alerts, company_id=args.company_id))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="aegis", description="Aegis ControlRisk CLI")
    p.add_argument("--data-dir", default="data",
                   help="path to synthetic data dir (default: data)")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="run pipeline for one company")
    a.add_argument("company_id")
    a.add_argument("--json", action="store_true",
                   help="emit full analysis dict as JSON")
    a.set_defaults(func=cmd_analyze)

    b = sub.add_parser("batch", help="run pipeline for the whole universe")
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--json", action="store_true",
                   help="emit compact result summary as JSON")
    b.set_defaults(func=cmd_batch)

    s = sub.add_parser("snapshot", help="snapshot management")
    s_sub = s.add_subparsers(dest="snapshot_cmd", required=True)

    s_save = s_sub.add_parser("save", help="save snapshot")
    s_save.add_argument("company_id")
    s_save.add_argument("--note", default="")
    s_save.set_defaults(func=cmd_snapshot_save)

    s_list = s_sub.add_parser("list", help="list snapshots")
    s_list.add_argument("--company", default=None,
                         help="filter to one company")
    s_list.set_defaults(func=cmd_snapshot_list)

    s_diff = s_sub.add_parser("diff", help="diff two snapshots")
    s_diff.add_argument("id_old")
    s_diff.add_argument("id_new")
    s_diff.add_argument("--json", action="store_true")
    s_diff.set_defaults(func=cmd_snapshot_diff)

    al = sub.add_parser("alerts", help="check alerts since last snapshot")
    al.add_argument("company_id")
    al.add_argument("--min-severity", default="moderate",
                    choices=["info", "moderate", "high", "critical"])
    al.set_defaults(func=cmd_alerts)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
