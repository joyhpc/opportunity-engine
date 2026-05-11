"""JSON output mode for the ODE CLI."""

from __future__ import annotations

import asyncio
import json

from ode import service
from ode.cli_io import CliInputError, load_profile_arg, split_csv_arg


def run_json_mode(args) -> None:
    """Run a supported command and print the raw service-layer result."""

    dispatch = {
        "create": lambda: asyncio.run(service.create_opportunity(
            name=args.name,
            domain=getattr(args, "domain", "") or "",
            keywords=[
                k.strip()
                for k in args.keywords.split(",")
            ] if getattr(args, "keywords", None) else [],
        )),
        "list": lambda: asyncio.run(service.list_opportunities()),
        "show": lambda: asyncio.run(service.show_opportunity(args.opp_id)),
        "status": lambda: asyncio.run(service.get_status()),
        "sources": lambda: asyncio.run(service.list_data_sources(
            status=getattr(args, "status", None),
            region=getattr(args, "region", None),
        )),
        "cases": lambda: asyncio.run(service.analyze_revenue_cases(
            path=getattr(args, "path", None),
            profile=load_profile_arg(args),
            region=getattr(args, "region", None),
            min_grade=getattr(args, "min_grade", None),
            top=getattr(args, "top", None),
        )),
        "pain": lambda: asyncio.run(service.listen_pains(
            hn_top=getattr(args, "hn_top", 50)
            if getattr(args, "hn_top", None) is not None else 50,
            subreddits=split_csv_arg(getattr(args, "reddit", None)),
            reddit_limit=getattr(args, "reddit_limit", 15)
            if getattr(args, "reddit_limit", None) is not None else 15,
            include_product_hunt=getattr(args, "product_hunt", True),
            product_hunt_limit=getattr(args, "product_hunt_limit", 30)
            if getattr(args, "product_hunt_limit", None) is not None else 30,
            keywords=split_csv_arg(getattr(args, "keywords", None)),
            profile=load_profile_arg(args),
            min_grade=getattr(args, "min_grade", "E") or "E",
            limit=getattr(args, "limit", 20)
            if getattr(args, "limit", None) is not None else 20,
        )),
        "daily": lambda: asyncio.run(service.run_daily_review(
            hn_top=getattr(args, "hn_top", 50)
            if getattr(args, "hn_top", None) is not None else 50,
            subreddits=split_csv_arg(getattr(args, "reddit", None)),
            reddit_limit=getattr(args, "reddit_limit", 15)
            if getattr(args, "reddit_limit", None) is not None else 15,
            include_product_hunt=getattr(args, "product_hunt", True),
            product_hunt_limit=getattr(args, "product_hunt_limit", 30)
            if getattr(args, "product_hunt_limit", None) is not None else 30,
            keywords=split_csv_arg(getattr(args, "keywords", None)),
            profile=load_profile_arg(args),
            min_grade=getattr(args, "min_grade", "E") or "E",
            limit=getattr(args, "limit", 20)
            if getattr(args, "limit", None) is not None else 20,
            cases_path=getattr(args, "cases_path", None),
            cases_region=getattr(args, "cases_region", None),
            cases_min_grade=getattr(args, "cases_min_grade", "B") or "B",
            cases_top=getattr(args, "cases_top", 10),
            include_explore=getattr(args, "explore", True),
            run_date=getattr(args, "date", None),
        )),
        "init-alerts": lambda: asyncio.run(service.initialize_warning_system(
            cases_path=getattr(args, "cases_path", None),
            profile=load_profile_arg(args),
            region=getattr(args, "region", None),
            min_grade=getattr(args, "min_grade", "C") or "C",
            top=getattr(args, "top", None),
            run_date=getattr(args, "date", None),
            reset=getattr(args, "reset", False),
        )),
        "portfolio": lambda: asyncio.run(service.get_portfolio()),
        "insights": lambda: asyncio.run(service.get_insights(args.opp_id)),
        "lens": lambda: asyncio.run(service.apply_lens(
            args.opp_id,
            profile=load_profile_arg(args),
        )),
        "refresh-gate": lambda: asyncio.run(service.refresh_gate(args.opp_id)),
    }
    func = dispatch.get(args.command)
    if func:
        try:
            result = func()
        except CliInputError as exc:
            result = {"ok": False, "data": {}, "message": str(exc)}
    else:
        result = {
            "ok": False,
            "message": f"--json not supported for '{args.command}' yet",
        }

    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))
