"""Workers — async functions that execute pipeline stages.

Workers are not independent processes/agents. They are async functions
that the Engine calls via asyncio.gather() for parallelism.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from ..core.models import (
    Opportunity, Signal, WorkerResult, _now_iso, _new_id,
)
from ..core.async_utils import run_blocking
from ..core.scoring import OpportunityScorer
from ..core.store import (
    save_opportunity, load_opportunity, save_signal,
    list_signals, reports_dir,
)
from ..tools import trend_scanner, market_sizer
from ..tools import financial_model, competitor_matrix, report_generator
from .gate import evaluate_gate


# ---------------------------------------------------------------------------
# scan_worker: signal collection + dedup + initial filtering
# ---------------------------------------------------------------------------

async def scan_worker(
    opp_id: str,
    keywords: list[str] | None = None,
    domain: str = "",
    hn_top: int = 0,
    subreddits: list[str] | None = None,
) -> WorkerResult:
    """SENSE stage: collect signals from multiple sources."""
    opp = load_opportunity(opp_id)
    if not opp:
        return WorkerResult(
            worker="scan", opportunity_id=opp_id,
            stage="SENSE", status="failed",
            message=f"Opportunity {opp_id} not found",
        )

    # Use opportunity keywords if none provided
    kws = keywords or opp.keywords
    if not kws:
        return WorkerResult(
            worker="scan", opportunity_id=opp_id,
            stage="SENSE", status="failed",
            message="No keywords provided for scanning",
        )

    raw_signals = await run_blocking(
        trend_scanner.scan_all,
        keywords=kws,
        domain=domain,
        hn_top=hn_top,
        subreddits=subreddits,
    )

    # Dedup by title
    seen = set()
    unique_signals = []
    for s in raw_signals:
        key = (s.get("title", ""), s.get("source", ""))
        if key not in seen:
            seen.add(key)
            unique_signals.append(s)

    # Save signals and link to opportunity
    signal_ids = []
    for s in unique_signals:
        sig = Signal(
            source=s.get("source", ""),
            keyword=s.get("keyword", ""),
            title=s.get("title", ""),
            momentum=s.get("momentum", 0),
            strength=s.get("strength", "弱"),
            url=s.get("url", ""),
            raw_data=s,
            opportunity_id=opp_id,
        )
        save_signal(sig)
        signal_ids.append(sig.id)

    # FIX #1: extend instead of replace to preserve historical signals
    existing = set(opp.signals)
    opp.signals = list(existing | set(signal_ids))
    opp.updated_at = _now_iso()
    save_opportunity(opp)

    # Evaluate SENSE gate
    gate_result = evaluate_gate("SENSE", signals=unique_signals)

    next_action = "advance" if gate_result["verdict"] == "GO" else (
        "hold" if gate_result["verdict"] == "MAYBE" else "kill"
    )

    if next_action == "advance":
        opp.advance("SCREEN", gate_result["verdict"], gate_result["score"])
        save_opportunity(opp)

    return WorkerResult(
        worker="scan",
        opportunity_id=opp_id,
        stage="SENSE",
        status="ok",
        scores={"signal_count": len(unique_signals), "gate": gate_result},
        artifacts=[],
        next_action=next_action,
        message=f"Found {len(unique_signals)} signals, gate={gate_result['verdict']}",
        data={"signals": unique_signals, "gate": gate_result},
    )


# ---------------------------------------------------------------------------
# eval_worker: market sizing + competitor scan + tech fit + economics + scoring
# ---------------------------------------------------------------------------

async def eval_worker(
    opp_id: str,
    depth: str = "screen",
    market_params: dict | None = None,
    competitor_data: dict | None = None,
    financial_params: dict | None = None,
    scores: dict | None = None,
) -> WorkerResult:
    """SCREEN/ANALYZE stage: evaluate opportunity across dimensions."""
    opp = load_opportunity(opp_id)
    if not opp:
        return WorkerResult(
            worker="eval", opportunity_id=opp_id,
            stage=depth.upper(), status="failed",
            message=f"Opportunity {opp_id} not found",
        )

    eval_data = {}
    artifacts = []

    # 1. Market sizing
    if market_params:
        if "market_size" in market_params:
            est = market_sizer.topdown_estimate(
                market_size=market_params["market_size"],
                segment_pct=market_params.get("segment_pct", 10),
                geo_pct=market_params.get("geo_pct", 30),
                capture_pct=market_params.get("capture_pct", 5),
            )
            opp.market = {
                "tam": est.tam, "sam": est.sam, "som": est.som,
                "growth_rate": market_params.get("growth_rate", 0),
                "confidence": est.confidence,
            }
            eval_data["market"] = opp.market
        elif "tam" in market_params:
            opp.market.update(market_params)
            eval_data["market"] = opp.market
    elif opp.market.get("tam", 0) > 0:
        eval_data["market"] = opp.market

    # 2. Competitor analysis
    if competitor_data:
        summary = competitor_matrix.build_competitor_summary(competitor_data)
        eval_data["competitors"] = summary

    # 3. Financial model
    if financial_params:
        ue = financial_model.UnitEconomics(
            arpu=financial_params.get("arpu", 29.99),
            cac=financial_params.get("cac", 50),
            cogs_per_user=financial_params.get("cogs_per_user",
                financial_params.get("arpu", 29.99) * financial_params.get("cogs_pct", 20) / 100),
            churn_rate=financial_params.get("churn_rate", 5.0),
        )
        config = financial_model.ProjectionConfig(
            arpu=ue.arpu,
            cac=ue.cac,
            cogs_pct=financial_params.get("cogs_pct", 20),
            churn_rate=ue.churn_rate,
            monthly_new_users=financial_params.get("monthly_new_users", 100),
            user_growth_rate=financial_params.get("user_growth_rate", 10),
            monthly_opex=financial_params.get("monthly_opex", 5000),
        )
        fin_summary = financial_model.build_financial_summary(ue, config)
        opp.financials = fin_summary
        eval_data["financials"] = fin_summary

    # 4. Opportunity scoring
    if not scores:
        # Auto-infer scores from signals using bridge heuristics
        from ..heuristics.bridge import infer_scores, scores_to_flat
        signals = list_signals(opp_id)
        if signals:
            inferred = infer_scores(
                [s.to_dict() for s in signals],
                domain=opp.domain,
                market_data=opp.market if opp.market.get("tam") else None,
                financial_data=opp.financials if opp.financials.get("ltv", 0) > 0 else None,
            )
            scores = scores_to_flat(inferred)
            eval_data["auto_inferred"] = True

    if scores:
        scoring_result = OpportunityScorer().apply(opp, scores)
        eval_data["scoring"] = scoring_result.to_dict()

        # Evaluate gate
        if depth == "screen":
            gate_result = evaluate_gate("SCREEN", scoring_result=scoring_result.to_dict())
        elif depth == "analyze":
            gate_result = evaluate_gate("ANALYZE",
                financials=opp.financials,
                regulatory=opp.regulatory)
        else:
            gate_result = {"verdict": "GO", "gate": depth.upper()}

        eval_data["gate"] = gate_result

        next_action = "advance" if gate_result["verdict"] == "GO" else (
            "hold" if gate_result["verdict"] == "MAYBE" else "kill"
        )
    else:
        gate_result = {"verdict": "MAYBE", "gate": depth.upper(),
                       "detail": "No scores provided, cannot evaluate gate"}
        next_action = "hold"
        eval_data["gate"] = gate_result

    # Save opportunity
    opp.updated_at = _now_iso()
    save_opportunity(opp)

    return WorkerResult(
        worker="eval",
        opportunity_id=opp_id,
        stage=depth.upper(),
        status="ok",
        scores=opp.scores,
        artifacts=artifacts,
        next_action=next_action,
        message=f"Evaluation at {depth} depth, gate={gate_result.get('verdict', 'N/A')}",
        data=eval_data,
    )


# ---------------------------------------------------------------------------
# report_worker: generate assessment reports
# ---------------------------------------------------------------------------

async def report_worker(
    opp_id: str,
    stage: str = "screen",
) -> WorkerResult:
    """Generate a report for the given opportunity and stage."""
    opp = load_opportunity(opp_id)
    if not opp:
        return WorkerResult(
            worker="report", opportunity_id=opp_id,
            stage=stage.upper(), status="failed",
            message=f"Opportunity {opp_id} not found",
        )

    # Gather data from opportunity
    scan_data = None
    eval_data = None

    signals = list_signals(opp_id)
    if signals:
        scan_data = {
            "signals": [s.to_dict() for s in signals],
        }

    if opp.scores or opp.market.get("tam", 0) > 0 or opp.financials.get("ltv", 0) > 0:
        # FIX #7: use stored weighted percentage instead of inaccurate unweighted formula
        weighted_pct = opp.scores.get("_weighted_pct", 0) if opp.scores else 0
        eval_data = {
            "scoring": {"percentage": weighted_pct, "verdict": ""},
            "market": opp.market,
            "financials": opp.financials,
        }

    # Generate report
    report_text = report_generator.generate_opportunity_report(
        opp.name,
        stage=stage,
        scan_data=scan_data,
        eval_data=eval_data,
    )

    # Append synthesis insights if data is available
    if opp.scores or opp.market.get("tam", 0) > 0:
        try:
            from ..heuristics.synthesize import synthesize, format_synthesis_report
            signals_data = [s.to_dict() for s in signals] if signals else []
            opp_data = {
                "scores": opp.scores,
                "market": opp.market,
                "financials": opp.financials,
                "regulatory": getattr(opp, "regulatory", {}),
                "signals": signals_data,
                "gate_log": opp.gate_log,
                "stage": opp.stage,
                "domain": opp.domain,
            }
            synthesis = synthesize(opp_data)
            if synthesis["contradictions"] or synthesis["blind_spots"]:
                report_text += "\n\n" + format_synthesis_report(synthesis)
        except Exception as e:
            logger.warning("Synthesis failed for %s: %s", opp_id, e)

    # Append latest saved DBS Lens diagnostic if present.
    try:
        from ..heuristics.dbs import latest_diagnostic, format_saved_diagnostic_report

        dbs_record = latest_diagnostic(opp.to_dict())
        if dbs_record:
            report_text += "\n\n" + format_saved_diagnostic_report(dbs_record)
    except Exception as e:
        logger.warning("DBS Lens report append failed for %s: %s", opp_id, e)

    # Save report
    rdir = reports_dir()
    report_path = rdir / f"{opp_id}_{stage}.md"
    report_path.write_text(report_text, encoding="utf-8")

    return WorkerResult(
        worker="report",
        opportunity_id=opp_id,
        stage=stage.upper(),
        status="ok",
        artifacts=[str(report_path)],
        next_action="hold",
        message=f"Report saved to {report_path}",
        data={"report_path": str(report_path), "report_text": report_text},
    )


# ---------------------------------------------------------------------------
# Engine: orchestrate workers
# ---------------------------------------------------------------------------

async def run_scan(opp_id: str, **kwargs) -> WorkerResult:
    """Convenience: run scan worker."""
    return await scan_worker(opp_id, **kwargs)


async def run_eval(opp_id: str, depth: str = "screen", **kwargs) -> WorkerResult:
    """Convenience: run eval worker."""
    return await eval_worker(opp_id, depth=depth, **kwargs)


async def run_report(opp_id: str, stage: str = "screen") -> WorkerResult:
    """Convenience: run report worker."""
    return await report_worker(opp_id, stage=stage)


async def run_pipeline(opp_id: str, through_stage: str = "SCREEN",
                       scan_kwargs: dict | None = None,
                       eval_kwargs: dict | None = None) -> list[WorkerResult]:
    """Run pipeline workers up through a given stage.

    SENSE always runs as the pipeline entry point.
    """
    from ..core.constants import STAGES

    results = []
    target_idx = STAGES.index(through_stage) if through_stage in STAGES else 1

    # SENSE (always runs as entry point)
    scan_result = await scan_worker(opp_id, **(scan_kwargs or {}))
    results.append(scan_result)
    if scan_result.next_action == "kill":
        return results

    # SCREEN
    if target_idx >= 1:
        eval_result = await eval_worker(opp_id, depth="screen", **(eval_kwargs or {}))
        results.append(eval_result)
        if eval_result.next_action == "kill":
            return results

    # ANALYZE
    if target_idx >= 2:
        analyze_result = await eval_worker(opp_id, depth="analyze", **(eval_kwargs or {}))
        results.append(analyze_result)

    return results
