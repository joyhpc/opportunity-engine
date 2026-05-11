"""JSON output mode for the ODE CLI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ode import service


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
            profile=_load_profile_arg(args),
            region=getattr(args, "region", None),
            min_grade=getattr(args, "min_grade", None),
            top=getattr(args, "top", None),
        )),
        "pain": lambda: asyncio.run(service.listen_pains(
            hn_top=getattr(args, "hn_top", 50)
            if getattr(args, "hn_top", None) is not None else 50,
            subreddits=[
                s.strip()
                for s in args.reddit.split(",")
            ] if getattr(args, "reddit", None) else None,
            reddit_limit=getattr(args, "reddit_limit", 15)
            if getattr(args, "reddit_limit", None) is not None else 15,
            include_product_hunt=getattr(args, "product_hunt", True),
            product_hunt_limit=getattr(args, "product_hunt_limit", 30)
            if getattr(args, "product_hunt_limit", None) is not None else 30,
            keywords=[
                k.strip()
                for k in args.keywords.split(",")
            ] if getattr(args, "keywords", None) else None,
            profile=_load_profile_arg(args),
            min_grade=getattr(args, "min_grade", "E") or "E",
            limit=getattr(args, "limit", 20)
            if getattr(args, "limit", None) is not None else 20,
        )),
        "portfolio": lambda: asyncio.run(service.get_portfolio()),
        "insights": lambda: asyncio.run(service.get_insights(args.opp_id)),
        "lens": lambda: asyncio.run(service.apply_lens(
            args.opp_id,
            profile=_load_profile_arg(args),
        )),
        "refresh-gate": lambda: asyncio.run(service.refresh_gate(args.opp_id)),
    }
    func = dispatch.get(args.command)
    if func:
        result = func()
    else:
        result = {
            "ok": False,
            "message": f"--json not supported for '{args.command}' yet",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def _load_profile_arg(args) -> dict | None:
    if getattr(args, "profile_json", None):
        return json.loads(args.profile_json)
    if getattr(args, "profile", None):
        return json.loads(Path(args.profile).read_text(encoding="utf-8"))
    return None
