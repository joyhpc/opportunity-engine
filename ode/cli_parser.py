"""Argument parser construction for the ODE CLI."""

from __future__ import annotations

import argparse

from ode.core.constants import EVIDENCE_GRADES, PAIN_EVIDENCE_GRADES


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ODE argument parser."""

    parser = argparse.ArgumentParser(
        prog="ode",
        description="Opportunity Discovery Engine",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("create", help="Create a new opportunity")
    p.add_argument("--name", required=True, help="Opportunity name")
    p.add_argument("--domain", help="Domain (e.g., education, health)")
    p.add_argument("--keywords", help="Keywords (comma-separated)")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Custom ID")

    sub.add_parser("list", help="List all opportunities")

    p = sub.add_parser("show", help="Show opportunity details")
    p.add_argument("opp_id", help="Opportunity ID or name")

    p = sub.add_parser("scan", help="Scan for signals")
    p.add_argument("--keywords", help="Keywords to scan (comma-separated)")
    p.add_argument("--domain", help="Domain filter")
    p.add_argument("--opp-id", help="Existing opportunity ID")
    p.add_argument("--name", help="Name for auto-created opportunity")
    p.add_argument("--hn-top", type=int, help="Scan HackerNews top N")
    p.add_argument("--reddit", help="Reddit subreddits (comma-separated)")

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

    p = sub.add_parser("report", help="Generate a report")
    p.add_argument("opp_id", help="Opportunity ID or name")
    p.add_argument("--stage", default="screen", help="Report stage")
    p.add_argument("--print", action="store_true", help="Print report to stdout")

    sub.add_parser("status", help="Show ODE status")
    p = sub.add_parser("sources", help="List opportunity data sources")
    p.add_argument(
        "--status",
        choices=["active", "optional", "utility", "manual", "planned"],
        help="Filter sources by registry status",
    )
    p.add_argument(
        "--region",
        choices=["global", "china"],
        help="Filter sources by region",
    )

    p = sub.add_parser("cases", help="Analyze revenue-proven cases")
    p.add_argument("--path", help="Revenue case JSON file")
    p.add_argument(
        "--region",
        choices=["global", "china"],
        help="Filter cases by region",
    )
    p.add_argument(
        "--min-grade",
        choices=list(EVIDENCE_GRADES),
        help="Minimum evidence grade to include",
    )
    p.add_argument("--top", type=int, help="Limit number of cases")
    p.add_argument("--profile", help="Path to founder profile JSON")
    p.add_argument("--profile-json", help="Inline founder profile JSON")

    p = sub.add_parser("dbs", help="Run the DBS diagnostic chain")
    p.add_argument("--text", required=True, help="Question, goal, or business direction to diagnose")
    p.add_argument("--opp-id", help="Optional opportunity ID or name")
    p.add_argument("--facts-json", help="Inline business facts JSON")
    p.add_argument("--product", help="Product or offer")
    p.add_argument("--price", help="Price")
    p.add_argument("--buyer", help="Buyer segment")
    p.add_argument("--acquisition", help="Acquisition channel")
    p.add_argument("--delivery", help="Delivery method")
    p.add_argument("--monthly-revenue", help="Current monthly revenue")
    p.add_argument("--demand", help="Demand or willingness-to-pay evidence")
    p.add_argument("--scalability", help="Repeatability or delegation notes")
    p.add_argument("--save", action="store_true", help="Save diagnostic to the opportunity")

    p = sub.add_parser("clarify", help="Clarify a fuzzy commercial goal")
    p.add_argument("--text", required=True, help="Goal or question to clarify")
    p.add_argument("--opp-id", help="Optional opportunity ID or name")
    p.add_argument("--save", action="store_true", help="Save diagnostic to the opportunity")

    p = sub.add_parser("diagnose", help="Apply DBS business diagnosis to an opportunity")
    p.add_argument("opp_id", help="Opportunity ID or name")
    p.add_argument("--facts-json", help="Inline business facts JSON")
    p.add_argument("--product", help="Product or offer")
    p.add_argument("--price", help="Price")
    p.add_argument("--buyer", help="Buyer segment")
    p.add_argument("--acquisition", help="Acquisition channel")
    p.add_argument("--delivery", help="Delivery method")
    p.add_argument("--monthly-revenue", help="Current monthly revenue")
    p.add_argument("--demand", help="Demand or willingness-to-pay evidence")
    p.add_argument("--scalability", help="Repeatability or delegation notes")
    p.add_argument("--save", action="store_true", help="Save diagnostic to the opportunity")

    p = sub.add_parser("deconstruct", help="Deconstruct fuzzy business concepts")
    p.add_argument("--text", required=True, help="Concept or sentence to deconstruct")
    p.add_argument("--opp-id", help="Optional opportunity ID or name")
    p.add_argument("--save", action="store_true", help="Save diagnostic to the opportunity")

    p = sub.add_parser("ai-hardware", help="Show the DBS-gated AI hardware opportunity workflow")
    p.add_argument("--region", default="shenzhen", help="Primary region or local market")
    p.add_argument("--team", default="solo_or_2_3_person_team", help="Founder/team constraint")

    sub.add_parser("portfolio", help="Show portfolio view")

    p = sub.add_parser("compare", help="Compare opportunities")
    p.add_argument("ids", help="Opportunity IDs (comma-separated)")

    p = sub.add_parser("explore", help="Open-ended opportunity exploration")
    p.add_argument("--hn-top", type=int, default=30, help="HackerNews top N")
    p.add_argument("--reddit", help="Subreddits (comma-separated)")
    p.add_argument("--keywords", help="Seed keywords (comma-separated)")
    p.add_argument("--output", help="Save report to file")

    p = sub.add_parser("pain", help="Listen for pain points across Reddit/HN/Product Hunt")
    p.add_argument("--hn-top", type=int, default=50, help="HackerNews top N")
    p.add_argument("--reddit", help="Subreddits (comma-separated)")
    p.add_argument("--reddit-limit", type=int, default=15, help="Posts per subreddit")
    p.add_argument("--keywords", help="Profile/seed keywords (comma-separated)")
    p.add_argument("--profile", help="Path to founder profile JSON")
    p.add_argument("--profile-json", help="Inline founder profile JSON")
    p.add_argument(
        "--min-grade",
        choices=list(PAIN_EVIDENCE_GRADES),
        default="E",
        help="Minimum evidence grade to include",
    )
    p.add_argument("--limit", type=int, default=20, help="Number of ranked signals")
    p.add_argument("--product-hunt-limit", type=int, default=30, help="Product Hunt feed items")
    p.add_argument("--product-hunt", dest="product_hunt", action="store_true", default=True)
    p.add_argument("--no-product-hunt", dest="product_hunt", action="store_false")
    p.add_argument("--output", help="Save report to file")

    p = sub.add_parser("daily", help="Run daily review and update opportunity warnings")
    p.add_argument("--hn-top", type=int, default=50, help="HackerNews top N")
    p.add_argument("--reddit", help="Reddit subreddits (comma-separated)")
    p.add_argument("--reddit-limit", type=int, default=15, help="Posts per subreddit")
    p.add_argument("--keywords", help="Profile/seed keywords (comma-separated)")
    p.add_argument("--profile", help="Path to founder profile JSON")
    p.add_argument("--profile-json", help="Inline founder profile JSON")
    p.add_argument(
        "--min-grade",
        choices=list(PAIN_EVIDENCE_GRADES),
        default="E",
        help="Minimum pain evidence grade to include",
    )
    p.add_argument("--limit", type=int, default=20, help="Number of ranked pain signals")
    p.add_argument("--product-hunt-limit", type=int, default=30, help="Product Hunt feed items")
    p.add_argument("--product-hunt", dest="product_hunt", action="store_true", default=True)
    p.add_argument("--no-product-hunt", dest="product_hunt", action="store_false")
    p.add_argument("--cases-path", help="Revenue case JSON file")
    p.add_argument("--cases-region", choices=["global", "china"], help="Filter revenue cases by region")
    p.add_argument(
        "--cases-min-grade",
        choices=list(EVIDENCE_GRADES),
        default="B",
        help="Minimum revenue evidence grade to include",
    )
    p.add_argument("--cases-top", type=int, default=10, help="Limit number of revenue cases; 0 skips cases")
    p.add_argument("--explore", dest="explore", action="store_true", default=True)
    p.add_argument("--no-explore", dest="explore", action="store_false")
    p.add_argument("--date", help=argparse.SUPPRESS)

    p = sub.add_parser("init-alerts", help="Bootstrap warning priors from revenue cases")
    p.add_argument("--path", "--cases-path", dest="cases_path", help="Revenue case JSON file")
    p.add_argument(
        "--region",
        choices=["global", "china"],
        help="Filter cases by region",
    )
    p.add_argument(
        "--min-grade",
        choices=list(EVIDENCE_GRADES),
        default="C",
        help="Minimum revenue evidence grade to learn from",
    )
    p.add_argument("--top", type=int, help="Limit number of cases")
    p.add_argument("--profile", help="Path to founder profile JSON")
    p.add_argument("--profile-json", help="Inline founder profile JSON")
    p.add_argument("--reset", action="store_true", help="Reset existing warning state before seeding")
    p.add_argument("--date", help=argparse.SUPPRESS)

    p = sub.add_parser("insights", help="Generate insights for an opportunity")
    p.add_argument("opp_id", help="Opportunity ID or name")

    p = sub.add_parser("lens", help="Apply Founder Fit Lens to an opportunity")
    p.add_argument("opp_id", help="Opportunity ID or name")
    p.add_argument("--profile", help="Path to founder profile JSON")
    p.add_argument("--profile-json", help="Inline founder profile JSON")

    p = sub.add_parser("experiment", help="Record a prototype iteration")
    p.add_argument("opp_id", help="Opportunity ID or name")
    p.add_argument("--version", required=True, help="Version label (e.g., v1, v2)")
    p.add_argument("--description", help="What was tested")
    p.add_argument("--cogs", type=float, help="Actual COGS per unit")
    p.add_argument("--outcome", choices=["pass", "fail", "partial"], help="Result")
    p.add_argument("--result", help="Summary of findings")
    p.add_argument("--metrics", help="Metrics JSON")

    p = sub.add_parser("record-actuals", help="Record actual financial data")
    p.add_argument("opp_id", help="Opportunity ID or name")
    p.add_argument("--cogs", type=float, help="Actual COGS per unit")
    p.add_argument("--arpu", type=float, help="Actual ARPU")
    p.add_argument("--units-sold", type=int, help="Units sold")
    p.add_argument("--notes", help="Notes")

    p = sub.add_parser("refresh-gate", help="Re-evaluate gate with current state")
    p.add_argument("opp_id", help="Opportunity ID or name")

    return parser
