"""Gate evaluator — decides GO / MAYBE / KILL at stage transitions."""

from __future__ import annotations

from ..core.constants import GATE_THRESHOLDS, SIGNAL_STRENGTH


def evaluate_sense_gate(signals: list[dict]) -> dict:
    """Gate 0: SENSE -> SCREEN. Need >= 3 strong signals."""
    strong = sum(1 for s in signals if s.get("strength") == "强")
    medium = sum(1 for s in signals if s.get("strength") == "中")

    # Count medium signals as 0.5 strong
    effective_strong = strong + medium * 0.5
    threshold = GATE_THRESHOLDS["SENSE"]["min_strong_signals"]

    if effective_strong >= threshold:
        verdict = "GO"
    elif effective_strong >= threshold * 0.6:
        verdict = "MAYBE"
    else:
        verdict = "KILL"

    return {
        "gate": "SENSE",
        "verdict": verdict,
        "score": round(effective_strong, 1),
        "threshold": threshold,
        "detail": f"strong={strong}, medium={medium}, effective={effective_strong:.1f}",
    }


def evaluate_screen_gate(scoring_result: dict) -> dict:
    """Gate 1: SCREEN -> ANALYZE. Based on opportunity score."""
    percentage = scoring_result.get("percentage", 0)
    redlines = scoring_result.get("redline_violations", [])
    thresholds = GATE_THRESHOLDS["SCREEN"]

    if redlines:
        verdict = "KILL"
    elif percentage >= thresholds["go"]:
        verdict = "GO"
    elif percentage >= thresholds["maybe"]:
        verdict = "MAYBE"
    else:
        verdict = "KILL"

    return {
        "gate": "SCREEN",
        "verdict": verdict,
        "score": percentage,
        "threshold_go": thresholds["go"],
        "threshold_maybe": thresholds["maybe"],
        "redlines": len(redlines),
    }


def evaluate_analyze_gate(financials: dict, regulatory: dict) -> dict:
    """Gate 2: ANALYZE -> VALIDATE. NPV > 0 and no P0 regulatory risk."""
    npv = financials.get("npv", 0)
    p0_risks = [r for r in regulatory.get("risks", []) if r.get("severity") == "P0"]

    npv_ok = npv > 0
    reg_ok = len(p0_risks) == 0

    if npv_ok and reg_ok:
        verdict = "GO"
    elif npv_ok and not reg_ok:
        verdict = "MAYBE"
    else:
        verdict = "KILL"

    return {
        "gate": "ANALYZE",
        "verdict": verdict,
        "npv": npv,
        "npv_positive": npv_ok,
        "p0_regulatory_risks": len(p0_risks),
    }


def evaluate_gate(stage: str, **kwargs) -> dict:
    """Dispatch to the appropriate gate evaluator."""
    if stage == "SENSE":
        return evaluate_sense_gate(kwargs.get("signals", []))
    elif stage == "SCREEN":
        return evaluate_screen_gate(kwargs.get("scoring_result", {}))
    elif stage == "ANALYZE":
        return evaluate_analyze_gate(
            kwargs.get("financials", {}),
            kwargs.get("regulatory", {}),
        )
    else:
        # Default pass-through for stages without gates
        return {
            "gate": stage,
            "verdict": "GO",
            "score": 0,
            "detail": "No gate defined for this stage",
        }
