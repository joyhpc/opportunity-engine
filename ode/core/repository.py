"""Repository abstractions over the YAML store."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ode.core.models import Opportunity, Signal
from ode.core.store import (
    find_opportunity_by_name,
    list_opportunities,
    list_signals,
    load_opportunity,
    save_opportunity,
)


@dataclass(frozen=True)
class DuplicateOpportunity:
    opportunity: Opportunity
    message: str
    similar_keywords: list[str] = field(default_factory=list)


class OpportunityRepository:
    """Small boundary for service code that needs opportunity persistence."""

    def get(self, opp_id_or_name: str) -> Opportunity | None:
        return load_opportunity(opp_id_or_name) or find_opportunity_by_name(opp_id_or_name)

    def list(self) -> list[Opportunity]:
        return list_opportunities()

    def save(self, opportunity: Opportunity) -> Path:
        return save_opportunity(opportunity)

    def signals_for(self, opportunity_id: str) -> list[Signal]:
        return list_signals(opportunity_id)

    def find_duplicate(self, name: str, keywords: list[str] | None = None) -> DuplicateOpportunity | None:
        keywords = keywords or []
        lowered_keywords = {keyword.lower() for keyword in keywords}
        for opportunity in self.list():
            if opportunity.name.lower() == name.lower():
                return DuplicateOpportunity(
                    opportunity=opportunity,
                    message=f"Existing opportunity '{opportunity.name}' (id={opportunity.id})",
                )
            if lowered_keywords:
                overlap = lowered_keywords & {keyword.lower() for keyword in opportunity.keywords}
                if len(overlap) / max(len(keywords), 1) >= 0.7:
                    return DuplicateOpportunity(
                        opportunity=opportunity,
                        message=(
                            f"Similar opportunity '{opportunity.name}' found "
                            "use --force to create anyway"
                        ),
                        similar_keywords=sorted(overlap),
                    )
        return None
