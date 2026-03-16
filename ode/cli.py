"""ODE CLI — Opportunity Discovery Engine command-line interface.

Usage:
    ode scan --keywords "AI companion,elderly care" --domain health
    ode eval <opp_id> --depth screen
    ode report <opp_id>
    ode status
    ode portfolio
    ode create --name "ElderMind" --domain "education" --keywords "elderly,cognitive"
    ode list
    ode show <opp_id>
"""

from __future__ import annotations

import argparse
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


def main():
    parser = argparse.ArgumentParser(
        prog="ode",
        description="Opportunity Discovery Engine",
    )
    sub = parser.add_subparsers(dest="command")

    # create
    p = sub.add_parser("create", help="Create a new opportunity")
    p.add_argument("--name", required=True, help="Opportunity name")
    p.add_argument("--domain", help="Domain (e.g., education, health)")
    p.add_argument("--keywords", help="Keywords (comma-separated)")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Custom ID")

    # list
    sub.add_parser("list", help="List all opportunities")

    # show
    p = sub.add_parser("show", help="Show opportunity details")
    p.add_argument("opp_id", help="Opportunity ID or name")

    # scan
    p = sub.add_parser("scan", help="Scan for signals")
    p.add_argument("--keywords", help="Keywords to scan (comma-separated)")
    p.add_argument("--domain", help="Domain filter")
    p.add_argument("--opp-id", help="Existing opportunity ID")
    p.add_argument("--name", help="Name for auto-created opportunity")
    p.add_argument("--hn-top", type=int, help="Scan HackerNews top N")
    p.add_argument("--reddit", help="Reddit subreddits (comma-separated)")

    # eval
    p = sub.add_parser("eval", help="Evaluate an opportunity")
    p.add_argument("opp_id", help="Opportunity ID or name")
    p.add_argument("--depth", choices=["screen", "analyze"], default="screen")
    p.add_argument("--tam", type=float, help="TAM in USD")
    p.add_argument("--segment-pct", type=float, help="Segment pct")
    p.add_argument("--geo-pct", type=float, help="Geo pct")
    p.add_argument("--arpu", type=float, help="Monthly ARPU")
    p.add_argument("--cac", type=float, help="CAC")
    p.add_argument("--churn", type=float, help="Monthly churn pct")
    p.add_argument("--cogs-pct", type=float, help="COGS pct")
    p.add_argument("--monthly-users", type=int, help="Monthly new users")
    p.add_argument("--growth-rate", type=float, help="User growth rate pct")
    p.add_argument("--opex", type=float, help="Monthly opex")
    p.add_argument("--scores", help="Scoring JSON")

    # report
    p = sub.add_parser("report", help="Generate a report")
    p.add_argument("opp_id", help="Opportunity ID or name")
    p.add_argument("--stage", default="screen", help="Report stage")
    p.add_argument("--print", action="store_true", help="Print report to stdout")

    # status
    sub.add_parser("status", help="Show ODE status")

    # portfolio
    sub.add_parser("portfolio", help="Show portfolio view")

    # compare
    p = sub.add_parser("compare", help="Compare opportunities")
    p.add_argument("ids", help="Opportunity IDs (comma-separated)")

    # explore
    p = sub.add_parser("explore", help="Open-ended opportunity exploration")
    p.add_argument("--hn-top", type=int, default=30, help="HackerNews top N")
    p.add_argument("--reddit", help="Subreddits (comma-separated)")
    p.add_argument("--keywords", help="Seed keywords (comma-separated)")
    p.add_argument("--output", help="Save report to file")

    # insights
    p = sub.add_parser("insights", help="Generate insights for an opportunity")
    p.add_argument("opp_id", help="Opportunity ID or name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "create": cmd_create,
        "list": cmd_list,
        "show": cmd_show,
        "scan": cmd_scan,
        "eval": cmd_eval,
        "report": cmd_report,
        "status": cmd_status,
        "portfolio": cmd_portfolio,
        "compare": cmd_compare,
        "explore": cmd_explore,
        "insights": cmd_insights,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
