"""Shared command registry for surfaces that consume ``ode.service``.

The registry keeps agent-facing adapters from re-implementing command routing.
CLI text mode can stay presentation-oriented, while JSON mode, Skills, MCP, and
API adapters can converge on these surface-neutral service calls.

``read_only`` means the command does not mutate ODE business entities such as
opportunities, signals, experiments, gate logs, or watchlists. It does not
promise a completely write-free process: low-level cache/database initialization
may still create local runtime files.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import shlex
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ode import service
from ode.cli_io import CliInputError, load_profile_values, split_csv_arg


CommandParams = dict[str, Any]
Executor = Callable[[CommandParams], Awaitable[dict]]


@dataclass(frozen=True)
class ServiceCommand:
    """A command that can be consumed by non-terminal surfaces."""

    name: str
    description: str
    read_only: bool
    execute: Executor


def _split_csv_value(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return split_csv_arg(str(value))


def _first_present(params: CommandParams, *names: str) -> Any:
    for name in names:
        if name in params and params[name] is not None:
            return params[name]
    return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _json_object(value: Any, flag_name: str) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        decoded = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise CliInputError(f"Invalid JSON for {flag_name}: {exc}") from exc
    if not isinstance(decoded, dict):
        raise CliInputError(f"{flag_name} must decode to an object")
    return decoded


def _diagnosis_facts(params: CommandParams) -> dict:
    facts = _json_object(params.get("facts_json"), "--facts-json") or {}
    for key in (
        "product",
        "price",
        "buyer",
        "acquisition",
        "delivery",
        "monthly_revenue",
        "demand",
        "scalability",
    ):
        value = params.get(key)
        if value is not None:
            facts[key] = value
    return facts


async def _create(params: CommandParams) -> dict:
    return await service.create_opportunity(
        name=params.get("name", ""),
        domain=params.get("domain") or "",
        keywords=_split_csv_value(params.get("keywords")) or [],
        description=params.get("description") or "",
        custom_id=params.get("id") or params.get("custom_id") or "",
    )


async def _list(params: CommandParams) -> dict:
    return await service.list_opportunities()


async def _show(params: CommandParams) -> dict:
    return await service.show_opportunity(params.get("opp_id", ""))


async def _status(params: CommandParams) -> dict:
    return await service.get_status()


async def _sources(params: CommandParams) -> dict:
    return await service.list_data_sources(
        status=params.get("status"),
        region=params.get("region"),
    )


async def _cases(params: CommandParams) -> dict:
    return await service.analyze_revenue_cases(
        path=params.get("path"),
        profile=load_profile_values(
            profile_json=params.get("profile_json"),
            profile=params.get("profile"),
        ),
        region=params.get("region"),
        min_grade=params.get("min_grade"),
        top=params.get("top"),
    )


async def _dbs(params: CommandParams) -> dict:
    return await service.run_dbs_session(
        params.get("text", ""),
        opp_id=params.get("opp_id"),
        facts=_diagnosis_facts(params),
        save=bool(params.get("save", False)),
    )


async def _clarify(params: CommandParams) -> dict:
    return await service.clarify_goal(
        params.get("text", ""),
        opp_id=params.get("opp_id"),
        save=bool(params.get("save", False)),
    )


async def _diagnose(params: CommandParams) -> dict:
    return await service.diagnose_business(
        params.get("opp_id", ""),
        facts=_diagnosis_facts(params),
        save=bool(params.get("save", False)),
    )


async def _deconstruct(params: CommandParams) -> dict:
    return await service.deconstruct_concept(
        params.get("text", ""),
        opp_id=params.get("opp_id"),
        save=bool(params.get("save", False)),
    )


async def _ai_hardware(params: CommandParams) -> dict:
    return await service.build_ai_hardware_workflow(
        region=params.get("region") or "shenzhen",
        team=params.get("team") or "solo_or_2_3_person_team",
    )


async def _portfolio(params: CommandParams) -> dict:
    return await service.get_portfolio()


async def _compare(params: CommandParams) -> dict:
    return await service.compare_opportunities(split_csv_arg(params.get("ids")) or [])


async def _insights(params: CommandParams) -> dict:
    return await service.get_insights(params.get("opp_id", ""))


async def _lens(params: CommandParams) -> dict:
    return await service.apply_lens(
        params.get("opp_id", ""),
        profile=load_profile_values(
            profile_json=params.get("profile_json"),
            profile=params.get("profile"),
        ),
    )


async def _scan(params: CommandParams) -> dict:
    return await service.scan(
        opp_id=params.get("opp_id") or None,
        keywords=_split_csv_value(params.get("keywords")),
        domain=params.get("domain") or "",
        hn_top=_int_or_none(params.get("hn_top")) or 0,
        subreddits=_split_csv_value(_first_present(params, "reddit", "subreddits")),
        name=params.get("name"),
    )


async def _eval(params: CommandParams) -> dict:
    return await service.evaluate(
        params.get("opp_id", ""),
        depth=params.get("depth") or "screen",
        tam=_float_or_none(params.get("tam")),
        segment_pct=_float_or_none(params.get("segment_pct")),
        geo_pct=_float_or_none(params.get("geo_pct")),
        arpu=_float_or_none(params.get("arpu")),
        cac=_float_or_none(params.get("cac")),
        churn=_float_or_none(params.get("churn")),
        cogs_pct=_float_or_none(params.get("cogs_pct")),
        monthly_users=_int_or_none(params.get("monthly_users")),
        growth_rate=_float_or_none(params.get("growth_rate")),
        opex=_float_or_none(params.get("opex")),
        scores=_json_object(params.get("scores"), "--scores"),
    )


async def _report(params: CommandParams) -> dict:
    return await service.generate_report(
        params.get("opp_id", ""),
        stage=params.get("stage") or "screen",
    )


async def _explore(params: CommandParams) -> dict:
    return await service.explore_signals(
        hn_top=_int_or_none(params.get("hn_top")) or 30,
        subreddits=_split_csv_value(_first_present(params, "reddit", "subreddits")),
        keywords=_split_csv_value(params.get("keywords")),
    )


async def _pain(params: CommandParams) -> dict:
    return await service.listen_pains(
        hn_top=_int_or_none(params.get("hn_top")) if params.get("hn_top") is not None else 50,
        subreddits=_split_csv_value(_first_present(params, "reddit", "subreddits")),
        reddit_limit=_int_or_none(params.get("reddit_limit")) if params.get("reddit_limit") is not None else 15,
        include_product_hunt=bool(params.get("product_hunt", True)),
        product_hunt_limit=(
            _int_or_none(params.get("product_hunt_limit"))
            if params.get("product_hunt_limit") is not None else 30
        ),
        keywords=_split_csv_value(params.get("keywords")),
        profile=load_profile_values(
            profile_json=params.get("profile_json"),
            profile=params.get("profile"),
        ),
        min_grade=params.get("min_grade") or "E",
        limit=_int_or_none(params.get("limit")) if params.get("limit") is not None else 20,
    )


async def _daily(params: CommandParams) -> dict:
    return await service.run_daily_review(
        hn_top=_int_or_none(params.get("hn_top")) if params.get("hn_top") is not None else 50,
        subreddits=_split_csv_value(_first_present(params, "reddit", "subreddits")),
        reddit_limit=_int_or_none(params.get("reddit_limit")) if params.get("reddit_limit") is not None else 15,
        include_product_hunt=bool(params.get("product_hunt", True)),
        product_hunt_limit=(
            _int_or_none(params.get("product_hunt_limit"))
            if params.get("product_hunt_limit") is not None else 30
        ),
        keywords=_split_csv_value(params.get("keywords")),
        profile=load_profile_values(
            profile_json=params.get("profile_json"),
            profile=params.get("profile"),
        ),
        min_grade=params.get("min_grade") or "E",
        limit=_int_or_none(params.get("limit")) if params.get("limit") is not None else 20,
        cases_path=params.get("cases_path"),
        cases_region=params.get("cases_region"),
        cases_min_grade=params.get("cases_min_grade") or "B",
        cases_top=_int_or_none(params.get("cases_top")) if params.get("cases_top") is not None else 10,
        include_explore=bool(params.get("explore", True)),
        run_date=params.get("date"),
    )


async def _init_alerts(params: CommandParams) -> dict:
    return await service.initialize_warning_system(
        cases_path=params.get("cases_path") or params.get("path"),
        profile=load_profile_values(
            profile_json=params.get("profile_json"),
            profile=params.get("profile"),
        ),
        region=params.get("region"),
        min_grade=params.get("min_grade") or "C",
        top=_int_or_none(params.get("top")),
        run_date=params.get("date"),
        reset=bool(params.get("reset", False)),
    )


async def _experiment(params: CommandParams) -> dict:
    return await service.add_experiment(
        params.get("opp_id", ""),
        version=params.get("version", ""),
        description=params.get("description") or "",
        cogs=_float_or_none(params.get("cogs")),
        outcome=params.get("outcome") or "partial",
        metrics=_json_object(params.get("metrics"), "--metrics"),
        result=params.get("result") or "",
    )


async def _record_actuals(params: CommandParams) -> dict:
    return await service.record_actuals(
        params.get("opp_id", ""),
        cogs=_float_or_none(params.get("cogs")),
        arpu=_float_or_none(params.get("arpu")),
        units_sold=_int_or_none(params.get("units_sold")),
        notes=params.get("notes") or "",
    )


async def _refresh_gate(params: CommandParams) -> dict:
    return await service.refresh_gate(params.get("opp_id", ""))


SERVICE_COMMANDS: dict[str, ServiceCommand] = {
    "create": ServiceCommand(
        name="create",
        description="Create a new opportunity",
        read_only=False,
        execute=_create,
    ),
    "list": ServiceCommand(
        name="list",
        description="List opportunities without mutating state",
        read_only=True,
        execute=_list,
    ),
    "show": ServiceCommand(
        name="show",
        description="Show one opportunity and its latest diagnostics",
        read_only=True,
        execute=_show,
    ),
    "status": ServiceCommand(
        name="status",
        description="Show repository runtime status",
        read_only=True,
        execute=_status,
    ),
    "sources": ServiceCommand(
        name="sources",
        description="List configured discovery sources",
        read_only=True,
        execute=_sources,
    ),
    "cases": ServiceCommand(
        name="cases",
        description="Analyze revenue-proven reference cases",
        read_only=True,
        execute=_cases,
    ),
    "dbs": ServiceCommand(
        name="dbs",
        description="Run the DBS diagnostic chain",
        read_only=False,
        execute=_dbs,
    ),
    "clarify": ServiceCommand(
        name="clarify",
        description="Clarify a fuzzy commercial goal",
        read_only=False,
        execute=_clarify,
    ),
    "diagnose": ServiceCommand(
        name="diagnose",
        description="Apply DBS business diagnosis to an opportunity",
        read_only=False,
        execute=_diagnose,
    ),
    "deconstruct": ServiceCommand(
        name="deconstruct",
        description="Deconstruct fuzzy business concepts",
        read_only=False,
        execute=_deconstruct,
    ),
    "ai-hardware": ServiceCommand(
        name="ai-hardware",
        description="Show the DBS-gated AI hardware opportunity workflow",
        read_only=True,
        execute=_ai_hardware,
    ),
    "portfolio": ServiceCommand(
        name="portfolio",
        description="Show portfolio ranking and summary",
        read_only=True,
        execute=_portfolio,
    ),
    "compare": ServiceCommand(
        name="compare",
        description="Compare opportunities side by side",
        read_only=True,
        execute=_compare,
    ),
    "insights": ServiceCommand(
        name="insights",
        description="Generate synthesis and reframe insights",
        read_only=True,
        execute=_insights,
    ),
    "lens": ServiceCommand(
        name="lens",
        description="Apply Founder Fit Lens without mutating the opportunity",
        read_only=True,
        execute=_lens,
    ),
    "scan": ServiceCommand(
        name="scan",
        description="Scan for signals",
        read_only=False,
        execute=_scan,
    ),
    "eval": ServiceCommand(
        name="eval",
        description="Evaluate an opportunity",
        read_only=False,
        execute=_eval,
    ),
    "report": ServiceCommand(
        name="report",
        description="Generate a report artifact",
        read_only=False,
        execute=_report,
    ),
    "explore": ServiceCommand(
        name="explore",
        description="Open-ended opportunity exploration",
        read_only=True,
        execute=_explore,
    ),
    "pain": ServiceCommand(
        name="pain",
        description="Listen for pain points across configured sources",
        read_only=True,
        execute=_pain,
    ),
    "daily": ServiceCommand(
        name="daily",
        description="Run daily review and update warning state",
        read_only=False,
        execute=_daily,
    ),
    "init-alerts": ServiceCommand(
        name="init-alerts",
        description="Bootstrap warning priors from revenue cases",
        read_only=False,
        execute=_init_alerts,
    ),
    "experiment": ServiceCommand(
        name="experiment",
        description="Record a prototype iteration",
        read_only=False,
        execute=_experiment,
    ),
    "record-actuals": ServiceCommand(
        name="record-actuals",
        description="Record actual financial data",
        read_only=False,
        execute=_record_actuals,
    ),
    "refresh-gate": ServiceCommand(
        name="refresh-gate",
        description="Re-evaluate gate with current state",
        read_only=False,
        execute=_refresh_gate,
    ),
}


def registered_command_names(*, read_only: bool | None = None) -> set[str]:
    """Return command names available through the shared registry."""

    if read_only is None:
        return set(SERVICE_COMMANDS)
    return {
        name
        for name, spec in SERVICE_COMMANDS.items()
        if spec.read_only is read_only
    }


def is_registered_command(name: str) -> bool:
    """Return whether a command is available through the shared registry."""

    return name in SERVICE_COMMANDS


async def run_registered_args_async(args: argparse.Namespace) -> dict:
    """Run a parsed argparse namespace through the shared registry."""

    return await run_registered_params_async(args.command, vars(args))


async def run_registered_params_async(command: str,
                                      params: CommandParams | None = None) -> dict:
    """Run a registered command from surface-neutral parameter values."""

    spec = SERVICE_COMMANDS.get(command)
    if not spec:
        return {
            "ok": False,
            "data": {},
            "message": f"Command is not registered for service dispatch: {command}",
        }
    return await spec.execute(params or {})


def run_registered_args(args: argparse.Namespace) -> dict:
    """Synchronous wrapper for terminal and Skill adapters."""

    return asyncio.run(run_registered_args_async(args))


def run_registered_params(command: str, params: CommandParams | None = None) -> dict:
    """Synchronous wrapper for non-async adapters.

    Async callers, such as future MCP/API adapters, should call
    ``run_registered_params_async`` directly.
    """

    return asyncio.run(run_registered_params_async(command, params))


def parse_registered_command(command: str, args_str: str = "") -> argparse.Namespace:
    """Parse a command string with the canonical CLI parser."""

    from ode.cli_parser import build_parser

    parser = build_parser()
    tokens = split_command_args(args_str)
    stderr = io.StringIO()
    stdout = io.StringIO()
    with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
        try:
            return parser.parse_args([command, *tokens])
        except SystemExit as exc:
            message = (stderr.getvalue() or stdout.getvalue()).strip()
            if not message:
                message = f"Argument parsing exited with status {exc.code}"
            raise CliInputError(message) from exc


def split_command_args(args_str: str = "") -> list[str]:
    """Split a Skill-style argument string without eating Windows paths."""

    if not args_str:
        return []
    posix = not _has_unquoted_windows_path(args_str)
    try:
        tokens = shlex.split(args_str, posix=posix)
    except ValueError as exc:
        raise CliInputError(f"Invalid command arguments: {exc}") from exc
    if not posix:
        tokens = [_strip_matching_quotes(token) for token in tokens]
    return tokens


def _has_unquoted_windows_path(text: str) -> bool:
    quote = ""
    for idx, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if (
            char.isalpha()
            and idx + 2 < len(text)
            and text[idx + 1] == ":"
            and text[idx + 2] == "\\"
        ):
            return True
    return False


def _strip_matching_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    return token


def run_registered_command_from_string(command: str, args_str: str = "") -> dict:
    """Parse and run a registered command from a Skill/MCP-style request."""

    if command not in SERVICE_COMMANDS:
        return {
            "ok": False,
            "data": {},
            "message": f"Command is not registered for service dispatch: {command}",
        }
    args = parse_registered_command(command, args_str)
    return run_registered_args(args)
