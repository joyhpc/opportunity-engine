"""Scoring adapter used by engine workers."""

from __future__ import annotations

from ode.core.models import Opportunity
from ode.tools.opportunity_scorer import ScoringResult, score_opportunity


class OpportunityScorer:
    """Apply scorecard output to an opportunity without exposing tool internals."""

    def score(self, opportunity_name: str, scores: dict) -> ScoringResult:
        return score_opportunity(opportunity_name, scores)

    def apply(self, opportunity: Opportunity, scores: dict) -> ScoringResult:
        result = self.score(opportunity.name, scores)
        opportunity.scores = self.to_opportunity_scores(result)
        return result

    @staticmethod
    def to_opportunity_scores(result: ScoringResult) -> dict:
        scores = {
            dim_name: dimension["average"]
            for dim_name, dimension in result.dimension_scores.items()
        }
        scores["_weighted_pct"] = result.percentage
        scores["_scoring_details"] = result.details
        return scores
