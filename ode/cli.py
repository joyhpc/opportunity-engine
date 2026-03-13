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


def cmd_create(args):
    """Create a new opportunity."""
    from ode.core.models import Opportunity
    from ode.core.store import save_opportunity

    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else []

    opp = Opportunity(
        name=args.name,
        domain=args.domain or "",
        description=args.description or "",
        keywords=keywords,
    )
    if args.id:
        opp.id = args.id

    path = save_opportunity(opp)
    print(f"Created opportunity: {opp.id}")
    print(f"  Name: {opp.name}")
    print(f"  Domain: {opp.domain}")
    print(f"  Keywords: {', '.join(keywords)}")
    print(f"  Saved: {path}")


def cmd_list(args):
    """List all opportunities."""
    from ode.core.store import list_opportunities

    opps = list_opportunities()
    if not opps:
        print("No opportunities found.")
        return

    print(f"{'ID':<15} {'Name':<25} {'Stage':<10} {'Status':<10}")
    print("-" * 60)
    for opp in opps:
        print(f"{opp.id:<15} {opp.name:<25} {opp.stage:<10} {opp.status:<10}")


def cmd_show(args):
    """Show opportunity details."""
    from ode.core.store import find_opportunity_by_name, load_opportunity

    opp = load_opportunity(args.opp_id) or find_opportunity_by_name(args.opp_id)
    if not opp:
        print(f"Opportunity not found: {args.opp_id}")
        sys.exit(1)

    print(f"ID: {opp.id}")
    print(f"Name: {opp.name}")
    print(f"Domain: {opp.domain}")
    print(f"Stage: {opp.stage}")
    print(f"Status: {opp.status}")
    print(f"Keywords: {', '.join(opp.keywords)}")
    print(f"Created: {opp.created_at}")
    print(f"Updated: {opp.updated_at}")

    if opp.scores:
        print(f"\nScores:")
        for dim, val in opp.scores.items():
            print(f"  {dim}: {val}")

    if opp.market.get("tam", 0) > 0:
        m = opp.market
        print(f"\nMarket:")
        print(f"  TAM: ${m['tam'] / 1e6:.0f}M")
        print(f"  SAM: ${m['sam'] / 1e6:.0f}M")
        print(f"  SOM: ${m['som'] / 1e6:.0f}M")

    if opp.financials.get("ltv", 0) > 0:
        f = opp.financials
        print(f"\nFinancials:")
        print(f"  LTV: ${f.get('ltv', 0):.0f}")
        print(f"  CAC: ${f.get('cac', 0):.0f}")
        print(f"  LTV/CAC: {f.get('ltv_cac_ratio', 0):.1f}x")

    if opp.gate_log:
        print(f"\nGate Log:")
        for g in opp.gate_log:
            print(f"  {g['gate']}: {g['verdict']} (score={g.get('score', 'N/A')}) at {g.get('ts', '')}")

    if opp.signals:
        print(f"\nSignals: {len(opp.signals)}")


def cmd_scan(args):
    """Run signal scanning."""
    from ode.core.store import find_opportunity_by_name, load_opportunity, save_opportunity
    from ode.core.models import Opportunity
    from ode.engine.workers import run_scan

    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else []

    # Find or create opportunity
    opp = None
    if args.opp_id:
        opp = load_opportunity(args.opp_id) or find_opportunity_by_name(args.opp_id)

    if not opp and keywords:
        # Auto-create from keywords
        name = args.name or keywords[0]
        opp = Opportunity(
            name=name,
            domain=args.domain or "",
            keywords=keywords,
        )
        save_opportunity(opp)
        print(f"Created opportunity: {opp.id} ({opp.name})")

    if not opp:
        print("Provide --keywords or --opp-id")
        sys.exit(1)

    # Run scan
    result = asyncio.run(run_scan(
        opp.id,
        keywords=keywords or None,
        domain=args.domain or "",
        hn_top=args.hn_top or 0,
        subreddits=[s.strip() for s in args.reddit.split(",")] if args.reddit else None,
    ))

    print(f"\nScan result: {result.status}")
    print(f"  Signals found: {result.scores.get('signal_count', 0)}")
    if "gate" in result.scores:
        g = result.scores["gate"]
        print(f"  Gate: {g.get('verdict', 'N/A')} (score={g.get('score', 'N/A')})")
    print(f"  Next action: {result.next_action}")
    print(f"  {result.message}")


def cmd_eval(args):
    """Evaluate an opportunity."""
    from ode.core.store import find_opportunity_by_name, load_opportunity
    from ode.engine.workers import run_eval

    opp = load_opportunity(args.opp_id) or find_opportunity_by_name(args.opp_id)
    if not opp:
        print(f"Opportunity not found: {args.opp_id}")
        sys.exit(1)

    # Parse optional params
    market_params = None
    if args.tam:
        market_params = {
            "market_size": args.tam,
            "segment_pct": args.segment_pct or 10,
            "geo_pct": args.geo_pct or 30,
        }

    financial_params = None
    if args.arpu:
        financial_params = {
            "arpu": args.arpu,
            "cac": args.cac or 50,
            "churn_rate": args.churn or 5.0,
            "cogs_pct": args.cogs_pct or 20,
            "monthly_new_users": args.monthly_users or 100,
            "user_growth_rate": args.growth_rate or 10,
            "monthly_opex": args.opex or 5000,
        }

    # Parse scores if provided
    scores = None
    if args.scores:
        try:
            scores = json.loads(args.scores)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON for --scores: {e}")
            sys.exit(1)

    result = asyncio.run(run_eval(
        opp.id,
        depth=args.depth,
        market_params=market_params,
        financial_params=financial_params,
        scores=scores,
    ))

    print(f"\nEval result ({args.depth}): {result.status}")
    if result.data.get("gate"):
        g = result.data["gate"]
        print(f"  Gate: {g.get('verdict', 'N/A')}")
    if result.data.get("scoring"):
        s = result.data["scoring"]
        print(f"  Score: {s.get('percentage', 0):.0f}/100 — {s.get('verdict', '')}")
    print(f"  Next action: {result.next_action}")
    print(f"  {result.message}")


def cmd_report(args):
    """Generate a report."""
    from ode.core.store import find_opportunity_by_name, load_opportunity
    from ode.engine.workers import run_report

    opp = load_opportunity(args.opp_id) or find_opportunity_by_name(args.opp_id)
    if not opp:
        print(f"Opportunity not found: {args.opp_id}")
        sys.exit(1)

    result = asyncio.run(run_report(opp.id, stage=args.stage))

    if result.status == "ok":
        report_path = result.data.get("report_path", "")
        print(f"Report generated: {report_path}")
        if args.print:
            print()
            print(result.data.get("report_text", ""))
    else:
        print(f"Report failed: {result.message}")


def cmd_status(args):
    """Show ODE status."""
    from ode.core.store import list_opportunities
    from ode.data.cache import Cache

    opps = list_opportunities()
    active = [o for o in opps if o.status == "active"]
    killed = [o for o in opps if o.status == "killed"]

    print("ODE Status")
    print("=" * 40)
    print(f"Total opportunities: {len(opps)}")
    print(f"  Active: {len(active)}")
    print(f"  Killed: {len(killed)}")

    if active:
        print(f"\nActive opportunities:")
        for o in active:
            print(f"  [{o.stage}] {o.name} ({o.id})")

    try:
        cache = Cache()
        stats = cache.stats()
        print(f"\nCache: {stats['valid']} entries ({stats['expired']} expired)")
    except Exception:
        pass


def cmd_portfolio(args):
    """Show portfolio view."""
    from ode.engine.portfolio import get_portfolio_summary, format_portfolio

    summaries = get_portfolio_summary()
    print(format_portfolio(summaries))


def cmd_compare(args):
    """Compare opportunities."""
    from ode.engine.portfolio import compare_opportunities

    ids = [i.strip() for i in args.ids.split(",")]
    print(compare_opportunities(ids))


def cmd_explore(args):
    """Open-ended opportunity exploration — no idea needed."""
    from ode.heuristics.explore import explore, format_exploration_report

    subreddits = [s.strip() for s in args.reddit.split(",")] if args.reddit else None
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    print("Scanning signals from HN, Reddit, and Trends...", file=sys.stderr)
    result = explore(
        hn_top=args.hn_top or 30,
        subreddits=subreddits,
        keywords=keywords,
    )

    report = format_exploration_report(result)
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nSaved to: {args.output}", file=sys.stderr)


def cmd_insights(args):
    """Generate insights (contradictions + blind spots) for an opportunity."""
    from ode.core.store import find_opportunity_by_name, load_opportunity, list_signals
    from ode.heuristics.synthesize import synthesize, format_synthesis_report
    from ode.heuristics.reframe import generate_reframe, format_reframe_report

    opp = load_opportunity(args.opp_id) or find_opportunity_by_name(args.opp_id)
    if not opp:
        print(f"Opportunity not found: {args.opp_id}")
        sys.exit(1)

    # Build opp_data dict for synthesis
    signals = list_signals(opp.id)
    opp_data = {
        "scores": opp.scores,
        "market": opp.market,
        "financials": opp.financials,
        "regulatory": opp.regulatory,
        "signals": [s.to_dict() for s in signals],
        "gate_log": opp.gate_log,
        "stage": opp.stage,
        "domain": opp.domain,
    }

    # Run synthesis
    synthesis = synthesize(opp_data)
    print(format_synthesis_report(synthesis))

    # Run reframe if score is borderline
    weighted_pct = opp.scores.get("_weighted_pct", 0) if opp.scores else 0
    if weighted_pct and weighted_pct < 70:
        verdict = "KILL" if weighted_pct < 50 else "MAYBE"
        # Find weakest dimension
        weakest = ""
        dim_scores = {k: v for k, v in opp.scores.items() if k != "_weighted_pct"}
        if dim_scores:
            weakest = min(dim_scores, key=lambda k: dim_scores[k])

        reframe = generate_reframe(
            scores=opp.scores,
            verdict=verdict,
            weakest_dimension=weakest,
        )
        print()
        print(format_reframe_report(reframe))


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
