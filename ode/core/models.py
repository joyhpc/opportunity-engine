"""ODE data models — Opportunity, Signal, Competitor, Evidence, WorkerResult."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


def _new_id(prefix: str = "") -> str:
    short = uuid.uuid4().hex[:8]
    return f"{prefix}{short}" if prefix else short


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    id: str = ""
    source: str = ""           # "google_trends" | "hackernews" | "reddit" | "manual"
    keyword: str = ""
    title: str = ""
    momentum: float = 0.0      # % change
    strength: str = "弱"       # "强" | "中" | "弱"
    ttl: int = 30              # days until stale
    raw_data: dict = field(default_factory=dict)
    url: str = ""
    fetched_at: str = ""
    opportunity_id: str = ""   # linked opportunity

    def __post_init__(self):
        if not self.id:
            self.id = _new_id("sig-")
        if not self.fetched_at:
            self.fetched_at = _now_iso()

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Competitor
# ---------------------------------------------------------------------------

@dataclass
class FundingRound:
    stage: str = ""       # "seed" | "A" | "B" ...
    amount: float = 0.0   # USD
    date: str = ""
    investors: list[str] = field(default_factory=list)


@dataclass
class Competitor:
    id: str = ""
    name: str = ""
    url: str = ""
    scores: dict = field(default_factory=dict)        # dimension -> 1-10
    funding: list[dict] = field(default_factory=list)  # FundingRound dicts
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    users_estimate: str = ""
    pricing: str = ""
    opportunity_id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = _new_id("comp-")

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    id: str = ""
    type: str = ""             # "market_report" | "trend_data" | "user_feedback" | ...
    source_url: str = ""
    structured_data: dict = field(default_factory=dict)
    confidence: float = 0.0    # 0-1
    fetched_at: str = ""
    opportunity_id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = _new_id("ev-")
        if not self.fetched_at:
            self.fetched_at = _now_iso()

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------

@dataclass
class Opportunity:
    id: str = ""
    name: str = ""
    domain: str = ""           # "education" | "health" | "fintech" | ...
    description: str = ""
    stage: str = "SENSE"       # current pipeline stage
    status: str = "active"     # "active" | "on_hold" | "killed" | "graduated"

    # 6-dimension scores (each 0-100)
    scores: dict = field(default_factory=dict)

    # Market sizing
    market: dict = field(default_factory=lambda: {
        "tam": 0, "sam": 0, "som": 0,
        "growth_rate": 0, "confidence": "低",
    })

    # Financial model
    financials: dict = field(default_factory=lambda: {
        "ltv": 0, "cac": 0, "ltv_cac_ratio": 0,
        "npv": 0, "irr": 0,
        "arpu": 0, "churn_rate": 0,
        "breakeven_months": None,
    })

    # Regulatory
    regulatory: dict = field(default_factory=lambda: {
        "risks": [],
        "compliance_notes": "",
    })

    # Linked entities
    signals: list[str] = field(default_factory=list)       # signal IDs
    competitors: list[str] = field(default_factory=list)    # competitor IDs
    evidence: list[str] = field(default_factory=list)       # evidence IDs

    # Metadata
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    # Gate log
    gate_log: list[dict] = field(default_factory=list)
    # e.g. [{"gate": "SCREEN", "verdict": "GO", "score": 75, "ts": "..."}]

    # Experiment / prototype iteration log
    experiments: list[dict] = field(default_factory=list)
    # e.g. [{"version": "v1", "description": "...", "cogs": 0.25,
    #         "outcome": "pass"|"fail"|"partial", "metrics": {}, "ts": "..."}]

    # Diagnostic lenses / advisory records
    diagnostics: list[dict] = field(default_factory=list)
    # e.g. [{"id": "diag-...", "source": "dbs_lens_v1",
    #         "type": "business_diagnosis", "created_at": "...", "result": {...}}]

    def __post_init__(self):
        if not self.id:
            self.id = _new_id("opp-")
        now = _now_iso()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return asdict(self)

    def advance(self, to_stage: str, verdict: str, score: float = 0):
        """Record a gate passage and advance to next stage."""
        from .constants import STAGES
        if to_stage not in STAGES:
            raise ValueError(f"Invalid stage: {to_stage}")
        self.gate_log.append({
            "gate": self.stage,
            "verdict": verdict,
            "score": score,
            "ts": _now_iso(),
        })
        self.stage = to_stage
        self.updated_at = _now_iso()


# ---------------------------------------------------------------------------
# WorkerResult
# ---------------------------------------------------------------------------

@dataclass
class WorkerResult:
    worker: str = ""           # "scan" | "eval" | "report"
    opportunity_id: str = ""
    stage: str = ""
    status: str = "ok"         # "ok" | "partial" | "failed"
    scores: dict = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    next_action: str = ""      # "advance" | "hold" | "kill"
    message: str = ""
    data: dict = field(default_factory=dict)  # arbitrary output

    def to_dict(self) -> dict:
        return asdict(self)
