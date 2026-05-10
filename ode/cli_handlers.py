"""CLI command handlers for ODE.

Handlers are intentionally thin: they translate parsed argparse namespaces into
service calls and format terminal output. Business behavior belongs in
``ode.service``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from ode import service


def cmd_create(args):
    """Create a new opportunity."""
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else []

    result = asyncio.run(service.create_opportunity(
        name=args.name,
        domain=args.domain or "",
        keywords=keywords,
        description=args.description or "",
        custom_id=args.id or "",
    ))

    d = result["data"]
    print(f"Created opportunity: {d['id']}")
    print(f"  Name: {d['name']}")
    print(f"  Domain: {d['domain']}")
    print(f"  Keywords: {', '.join(d['keywords'])}")
    print(f"  Saved: {d['path']}")


def cmd_list(args):
    """List all opportunities."""
    result = asyncio.run(service.list_opportunities())
    opps = result["data"]["opportunities"]

    if not opps:
        print("No opportunities found.")
        return

    print(f"{'ID':<15} {'Name':<25} {'Stage':<10} {'Status':<10}")
    print("-" * 60)
    for opp in opps:
        print(f"{opp['id']:<15} {opp['name']:<25} {opp['stage']:<10} {opp['status']:<10}")


def cmd_show(args):
    """Show opportunity details."""
    result = asyncio.run(service.show_opportunity(args.opp_id))
    if not result["ok"]:
        print(result["message"])
        sys.exit(1)

    d = result["data"]
    print(f"ID: {d['id']}")
    print(f"Name: {d['name']}")
    print(f"Domain: {d['domain']}")
    print(f"Stage: {d['stage']}")
    print(f"Status: {d['status']}")
    print(f"Keywords: {', '.join(d['keywords'])}")
    print(f"Created: {d['created_at']}")
    print(f"Updated: {d['updated_at']}")

    if d["scores"]:
        print(f"\nScores:")
        for dim, val in d["scores"].items():
            print(f"  {dim}: {val}")

    market = d.get("market", {})
    if market.get("tam", 0) > 0:
        print(f"\nMarket:")
        print(f"  TAM: ${market['tam'] / 1e6:.0f}M")
        print(f"  SAM: ${market['sam'] / 1e6:.0f}M")
        print(f"  SOM: ${market['som'] / 1e6:.0f}M")

    financials = d.get("financials", {})
    if financials.get("ltv", 0) > 0:
        print(f"\nFinancials:")
        print(f"  LTV: ${financials.get('ltv', 0):.0f}")
        print(f"  CAC: ${financials.get('cac', 0):.0f}")
        print(f"  LTV/CAC: {financials.get('ltv_cac_ratio', 0):.1f}x")

    if d["gate_log"]:
        print(f"\nGate Log:")
        for g in d["gate_log"]:
            print(f"  {g['gate']}: {g['verdict']} (score={g.get('score', 'N/A')}) at {g.get('ts', '')}")

    if d["signal_count"]:
        print(f"\nSignals: {d['signal_count']}")

    experiments = d.get("experiments", [])
    if experiments:
        print(f"\nExperiments ({len(experiments)}):")
        for e in experiments:
            icon = {"pass": "+", "fail": "x", "partial": "~"}.get(e.get("outcome", ""), "?")
            cogs_str = f" COGS=${e['cogs']:.2f}" if e.get("cogs") else ""
            print(f"  [{icon}] {e.get('version', '?')}: {e.get('result', e.get('description', ''))[:60]}{cogs_str}")

    actuals = d.get("financials", {}).get("actuals", {})
    if actuals and actuals.get("cogs_per_unit") is not None:
        print(f"\nActuals:")
        print(f"  COGS/unit: ${actuals['cogs_per_unit']:.2f}")
        if actuals.get("cogs_variance_pct") is not None:
            print(f"  vs estimate: {actuals['cogs_variance_pct']:+.1f}%")
        if actuals.get("notes"):
            print(f"  Notes: {actuals['notes']}")


def cmd_scan(args):
    """Run signal scanning."""
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else []

    result = asyncio.run(service.scan(
        opp_id=args.opp_id or None,
        keywords=keywords or None,
        domain=args.domain or "",
        hn_top=args.hn_top or 0,
        subreddits=[s.strip() for s in args.reddit.split(",")] if args.reddit else None,
        name=args.name,
    ))

    if not result["ok"]:
        print(result["message"])
        sys.exit(1)

    d = result["data"]
    if d.get("auto_created"):
        print(f"Created opportunity: {d['opp_id']}")

    print(f"\nScan result: {d['status']}")
    print(f"  Signals found: {d['signal_count']}")
    if d.get("gate"):
        g = d["gate"]
        print(f"  Gate: {g.get('verdict', 'N/A')} (score={g.get('score', 'N/A')})")
    print(f"  Next action: {d['next_action']}")
    print(f"  {d['message']}")


def cmd_eval(args):
    """Evaluate an opportunity."""
    # Parse scores if provided
    scores = None
    if args.scores:
        try:
            scores = json.loads(args.scores)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON for --scores: {e}")
            sys.exit(1)

    result = asyncio.run(service.evaluate(
        args.opp_id,
        depth=args.depth,
        tam=args.tam,
        segment_pct=args.segment_pct,
        geo_pct=args.geo_pct,
        arpu=args.arpu,
        cac=args.cac,
        churn=args.churn,
        cogs_pct=args.cogs_pct,
        monthly_users=args.monthly_users,
        growth_rate=args.growth_rate,
        opex=args.opex,
        scores=scores,
    ))

    if not result["ok"]:
        print(result["message"])
        sys.exit(1)

    d = result["data"]
    print(f"\nEval result ({d['depth']}): {d['status']}")
    if d.get("gate"):
        g = d["gate"]
        print(f"  Gate: {g.get('verdict', 'N/A')}")
    if d.get("scoring"):
        s = d["scoring"]
        print(f"  Score: {s.get('percentage', 0):.0f}/100 — {s.get('verdict', '')}")
    print(f"  Next action: {d['next_action']}")
    print(f"  {d['message']}")


def cmd_report(args):
    """Generate a report."""
    result = asyncio.run(service.generate_report(args.opp_id, stage=args.stage))

    if not result["ok"]:
        print(result["message"])
        sys.exit(1)

    d = result["data"]
    print(f"Report generated: {d['report_path']}")
    if args.print:
        print()
        print(d.get("report_text", ""))


def cmd_status(args):
    """Show ODE status."""
    result = asyncio.run(service.get_status())
    d = result["data"]

    print("ODE Status")
    print("=" * 40)
    print(f"Total opportunities: {d['total']}")
    print(f"  Active: {d['active_count']}")
    print(f"  Killed: {d['killed_count']}")

    if d["active"]:
        print(f"\nActive opportunities:")
        for o in d["active"]:
            print(f"  [{o['stage']}] {o['name']} ({o['id']})")

    cache = d.get("cache", {})
    if cache:
        print(f"\nCache: {cache['valid']} entries ({cache['expired']} expired)")


def cmd_sources(args):
    """List configured opportunity data sources."""
    result = asyncio.run(service.list_data_sources(status=args.status, region=args.region))
    print(result["data"]["formatted"])


def cmd_cases(args):
    """Analyze revenue-proven reference cases."""
    profile = _load_profile_arg(args)
    result = asyncio.run(service.analyze_revenue_cases(
        path=args.path,
        profile=profile,
        region=args.region,
        min_grade=args.min_grade,
        top=args.top,
    ))
    print(result["data"]["formatted"])


def cmd_portfolio(args):
    """Show portfolio view."""
    result = asyncio.run(service.get_portfolio())
    print(result["data"]["formatted"])


def cmd_compare(args):
    """Compare opportunities."""
    ids = [i.strip() for i in args.ids.split(",")]
    result = asyncio.run(service.compare_opportunities(ids))
    print(result["data"]["formatted"])


def cmd_explore(args):
    """Open-ended opportunity exploration — no idea needed."""
    subreddits = [s.strip() for s in args.reddit.split(",")] if args.reddit else None
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    print("Scanning signals from HN, Reddit, and Trends...", file=sys.stderr)
    result = asyncio.run(service.explore_signals(
        hn_top=args.hn_top or 30,
        subreddits=subreddits,
        keywords=keywords,
    ))

    report = result["data"]["formatted"]
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nSaved to: {args.output}", file=sys.stderr)


def cmd_insights(args):
    """Generate insights (contradictions + blind spots) for an opportunity."""
    from ode.heuristics.synthesize import format_synthesis_report
    from ode.heuristics.reframe import format_reframe_report
    from ode.heuristics.bridge import format_quick_assess_report

    result = asyncio.run(service.get_insights(args.opp_id))
    if not result["ok"]:
        print(result["message"])
        sys.exit(1)

    d = result["data"]

    print(format_synthesis_report(d["synthesis"]))

    if d.get("quick_assess"):
        print()
        print(format_quick_assess_report(d["quick_assess"]))

    if d.get("reframe"):
        print()
        print(format_reframe_report(d["reframe"]))


def cmd_lens(args):
    """Apply Founder Fit Lens to an opportunity."""
    from ode.heuristics.fit_lens import LensResult, format_lens_report

    profile = _load_profile_arg(args)
    result = asyncio.run(service.apply_lens(args.opp_id, profile=profile))
    if not result["ok"]:
        print(result["message"], file=sys.stderr)
        sys.exit(1)

    lens = LensResult(**result["data"]["lens"])
    print(format_lens_report(lens))


def cmd_experiment(args):
    """Record a prototype iteration."""
    metrics = json.loads(args.metrics) if args.metrics else None
    result = asyncio.run(service.add_experiment(
        args.opp_id, version=args.version,
        description=args.description or "",
        cogs=args.cogs, outcome=args.outcome or "partial",
        metrics=metrics, result=args.result or "",
    ))
    if not result["ok"]:
        print(result["message"], file=sys.stderr)
        sys.exit(1)
    d = result["data"]
    print(f"Experiment {d['version']} recorded ({d['outcome']})")
    print(f"  Total experiments: {d['experiment_count']}")


def cmd_record_actuals(args):
    """Record actual financial data."""
    result = asyncio.run(service.record_actuals(
        args.opp_id, cogs=args.cogs, arpu=args.arpu,
        units_sold=args.units_sold, notes=args.notes or "",
    ))
    if not result["ok"]:
        print(result["message"], file=sys.stderr)
        sys.exit(1)
    actuals = result["data"].get("actuals", {})
    print("Actuals recorded:")
    for k, v in actuals.items():
        if v is not None and v != "":
            print(f"  {k}: {v}")


def cmd_refresh_gate(args):
    """Re-evaluate gate with current state."""
    result = asyncio.run(service.refresh_gate(args.opp_id))
    if not result["ok"]:
        print(result["message"], file=sys.stderr)
        sys.exit(1)
    d = result["data"]
    if d["verdict_changed"]:
        print(f"Gate CHANGED: {d['previous_verdict']} → {d['new_verdict']}")
    else:
        print(f"Gate unchanged: {d['new_verdict']}")
    if d.get("detail"):
        print(f"  {d['detail']}")
    if d.get("passed_experiments"):
        print(f"  Passed experiments: {d['passed_experiments']}")


COMMANDS = {
    "create": cmd_create,
    "list": cmd_list,
    "show": cmd_show,
    "scan": cmd_scan,
    "eval": cmd_eval,
    "report": cmd_report,
    "status": cmd_status,
    "sources": cmd_sources,
    "cases": cmd_cases,
    "portfolio": cmd_portfolio,
    "compare": cmd_compare,
    "explore": cmd_explore,
    "insights": cmd_insights,
    "lens": cmd_lens,
    "experiment": cmd_experiment,
    "record-actuals": cmd_record_actuals,
    "refresh-gate": cmd_refresh_gate,
}


def run_command(args) -> None:
    """Run the command selected by the parsed CLI namespace."""

    if getattr(args, "json", False):
        from ode.cli_json import run_json_mode

        run_json_mode(args)
        return

    cmd_func = COMMANDS.get(args.command)
    if not cmd_func:
        raise ValueError(f"Unknown command: {args.command}")

    cmd_func(args)


def _load_profile_arg(args) -> dict | None:
    if getattr(args, "profile_json", None):
        try:
            return json.loads(args.profile_json)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON for --profile-json: {exc}", file=sys.stderr)
            sys.exit(1)

    if getattr(args, "profile", None):
        try:
            return json.loads(Path(args.profile).read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"Cannot read --profile: {exc}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as exc:
            print(f"Invalid profile JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    return None
