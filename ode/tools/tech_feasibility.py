"""Tech feasibility assessment tool."""

from __future__ import annotations


def assess_feasibility(
    required_skills: list[str] | None = None,
    available_skills: list[str] | None = None,
    estimated_months: float = 3,
    team_size: int = 1,
) -> dict:
    """Assess technical feasibility of an opportunity.

    Returns a dict with fit_score (1-10), gaps, and recommendation.
    """
    required = set(s.lower() for s in (required_skills or []))
    available = set(s.lower() for s in (available_skills or []))

    if not required:
        return {
            "fit_score": 5,
            "gaps": [],
            "covered": [],
            "recommendation": "No skill requirements specified, defaulting to neutral.",
        }

    covered = required & available
    gaps = required - available
    coverage = len(covered) / len(required) if required else 0

    # Score: coverage * 8 + time/team bonus
    base_score = coverage * 8
    if estimated_months <= 1:
        base_score += 2
    elif estimated_months <= 3:
        base_score += 1

    fit_score = min(10, max(1, round(base_score)))

    if fit_score >= 8:
        rec = "Strong fit — core skills available, timeline realistic."
    elif fit_score >= 5:
        rec = f"Partial fit — {len(gaps)} skill gap(s) need addressing."
    else:
        rec = "Weak fit — significant skill gaps and/or timeline pressure."

    return {
        "fit_score": fit_score,
        "gaps": sorted(gaps),
        "covered": sorted(covered),
        "coverage_pct": round(coverage * 100, 1),
        "recommendation": rec,
    }
