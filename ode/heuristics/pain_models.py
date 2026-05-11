"""Data models for pain listener analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ode.core.recommendations import WATCH


@dataclass
class PainSignal:
    title: str
    url: str = ""
    source: str = ""
    source_id: str = ""
    source_type: str = ""
    snippet: str = ""
    audience: str = ""
    pain_markers: list[str] = field(default_factory=list)
    request_markers: list[str] = field(default_factory=list)
    buyer_markers: list[str] = field(default_factory=list)
    commercial_markers: list[str] = field(default_factory=list)
    downrank_markers: list[str] = field(default_factory=list)
    workaround_markers: list[str] = field(default_factory=list)
    urgency_markers: list[str] = field(default_factory=list)
    keyword_matches: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    pain_score: float = 0.0
    founder_fit: float = 0.0
    priority_score: float = 0.0
    evidence_grade: str = "E"
    cluster_size: int = 1
    source_diversity: int = 1
    recommendation: str = WATCH
    reasons: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
