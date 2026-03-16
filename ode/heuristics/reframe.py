"""Reframe — suggest repositioning when Gate returns MAYBE or KILL.

Instead of just "MAYBE — needs more validation", this module analyzes
WHY it's borderline and suggests concrete pivots.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Domain adjacency map for lateral moves
# ---------------------------------------------------------------------------

DOMAIN_ADJACENCY = {
    "education": ["health", "saas", "creator"],
    "health": ["education", "climate", "saas"],
    "fintech": ["saas", "ecommerce"],
    "devtools": ["saas", "ai_ml", "creator"],
    "ai_ml": ["devtools", "saas", "education"],
    "hardware": ["robotics", "climate", "devtools"],
    "robotics": ["hardware", "climate", "ai_ml"],
    "creator": ["education", "saas", "ecommerce"],
    "saas": ["devtools", "fintech", "education"],
    "ecommerce": ["saas", "fintech", "creator"],
    "climate": ["hardware", "health", "saas"],
}

# ---------------------------------------------------------------------------
# Inversion map — flip the demand pattern perspective
# ---------------------------------------------------------------------------

INVERSION_MAP = {
    "decision_proxy": "Don't help buyers choose — help sellers understand what buyers want",
    "comparison":     "Don't help users compare — help products differentiate their positioning",
    "capability_gap": "Don't teach users how to do it — teach creators how to teach",
    "avoidance":      "Don't help buyers avoid bad products — help sellers fix quality",
    "curation":       "Don't curate for consumers — help producers get curated",
    "info_gap":       "Don't surface hidden info for readers — help writers identify what's missing",
}


# ---------------------------------------------------------------------------
# Reframe strategies per weak dimension
# ---------------------------------------------------------------------------

REFRAME_STRATEGIES = {
    "Market Attractiveness": [
        {
            "if_low": "tam_size",
            "strategy": "Niche Down",
            "description": "Target a micro-segment where you can be #1. A $10M niche you own beats a $1B market you can't enter.",
            "actions": [
                "Identify the most specific user persona from your signals",
                "Find a community of 1,000 passionate users (subreddit, Discord, forum)",
                "Price 3-5x higher for this niche (they'll pay for specificity)",
            ],
        },
        {
            "if_low": "growth",
            "strategy": "Ride an Adjacent Wave",
            "description": "The core market may be flat, but an adjacent trend could create new demand.",
            "actions": [
                "Look for AI/automation angle on a mature market",
                "Check if regulatory changes are creating new needs",
                "Scan for demographic shifts (aging, Gen Z, remote work)",
            ],
        },
        {
            "if_low": "timing",
            "strategy": "Create Urgency",
            "description": "Market timing is about perception. Can you create a catalyst event?",
            "actions": [
                "Launch alongside a relevant industry event or regulation deadline",
                "Build on a trending topic (use your scan signals)",
                "Position as 'before X happens, you need this'",
            ],
        },
    ],
    "Competitive Landscape": [
        {
            "if_low": "intensity",
            "strategy": "Asymmetric Entry",
            "description": "Don't compete on features. Compete on a dimension incumbents can't match.",
            "actions": [
                "Go 10x cheaper (if they're enterprise, go SMB)",
                "Go 10x simpler (if they're complex, go opinionated)",
                "Go to an underserved geography or language",
                "Bundle with something they can't (your unique skill/access)",
            ],
        },
        {
            "if_low": "moat_potential",
            "strategy": "Build Community Moat",
            "description": "If tech moat is weak, build a people moat. Communities are harder to clone than code.",
            "actions": [
                "Start a free community around the problem (not the product)",
                "Create content that becomes the go-to resource",
                "Design the product so users' data/content grows its value",
            ],
        },
    ],
    "Capability Fit": [
        {
            "if_low": "skill_match",
            "strategy": "Partner or Reposition",
            "description": "You don't need all skills. You need the right partnership or a different angle.",
            "actions": [
                "Find a co-founder who fills the gap (AngelList, Indie Hackers)",
                "Use no-code/low-code to bridge technical gaps",
                "Reposition to a segment where YOUR skills are the advantage",
            ],
        },
        {
            "if_low": "time_to_market",
            "strategy": "Shrink the V1",
            "description": "You're building too much. What's the smallest thing that delivers value?",
            "actions": [
                "Cut scope to ONE user, ONE problem, ONE workflow",
                "Ship a manual-behind-the-scenes version first",
                "Use existing tools (Typeform + Zapier + Notion) as V0",
            ],
        },
    ],
    "Economic Viability": [
        {
            "if_low": "ltv_cac",
            "strategy": "Flip the Acquisition Model",
            "description": "High CAC usually means wrong channel, not wrong product.",
            "actions": [
                "Try content/SEO instead of paid ads",
                "Build a free tool that generates leads",
                "Partner with someone who already has your audience",
                "Go product-led growth (free tier that sells itself)",
            ],
        },
        {
            "if_low": "margin",
            "strategy": "Move Up the Value Chain",
            "description": "Low margin = commodity. Move from 'tool' to 'outcome'.",
            "actions": [
                "Charge for results instead of access (performance pricing)",
                "Add a service/consulting layer on top of the tool",
                "Bundle multiple low-margin features into a high-margin platform",
            ],
        },
    ],
    "Validation Strength (YC MVT)": [
        {
            "if_low": "pain_evidence",
            "strategy": "Pain Discovery Sprint",
            "description": "You might be solving a problem nobody has. Validate the PROBLEM before the SOLUTION.",
            "actions": [
                "Post in 3 communities: describe the problem, ask 'does anyone else deal with this?'",
                "Do 5 user interviews this week (start with 'tell me about the last time you...')",
                "Search Reddit/Twitter for complaints related to your space",
            ],
        },
        {
            "if_low": "willingness_to_pay",
            "strategy": "Pre-sell Before Building",
            "description": "Talk is cheap. Commitment isn't. Get money before code.",
            "actions": [
                "Create a landing page with a 'Buy Now' button ($0 charged, just track clicks)",
                "Offer 3 people a manual version of the service at full price",
                "Ask: 'If I built X, would you pay $Y/mo?' — then ask for a deposit",
            ],
        },
    ],
    "AI-Native Potential (a16z)": [
        {
            "if_low": "system_rethink",
            "strategy": "Rethink the Workflow",
            "description": "Don't add AI to an existing tool. Reimagine the workflow AS IF AI existed from day one.",
            "actions": [
                "Map the current user workflow: which steps exist only because humans can't X?",
                "Design the '10x version' where AI removes entire steps",
                "Look for 'glue work' — tasks users do between tools",
            ],
        },
    ],
}


def generate_lateral_moves(domain: str,
                           demand_pattern: str = "",
                           weakest_dimension: str = "") -> list[dict]:
    """Suggest opportunities in adjacent domains with the same need pattern.

    When the current path is blocked (MAYBE/KILL), lateral moves
    propose the same demand pattern in a neighboring domain.
    """
    adjacent = DOMAIN_ADJACENCY.get(domain, [])
    if not adjacent:
        return []

    moves = []
    for adj_domain in adjacent:
        move = {
            "from_domain": domain,
            "to_domain": adj_domain,
            "strategy": f"Apply {domain} insight to {adj_domain}",
            "description": (
                f"Your signal analysis in {domain} revealed demand patterns "
                f"that may exist in {adj_domain} with less competition."
            ),
        }
        if demand_pattern:
            move["demand_pattern"] = demand_pattern
            move["description"] = (
                f"The '{demand_pattern.replace('_', ' ')}' need you found in {domain} "
                f"likely also exists in {adj_domain} — but fewer people are serving it there."
            )
        if weakest_dimension:
            move["rationale"] = (
                f"Your weakest area ({weakest_dimension}) may score better "
                f"in {adj_domain} due to different market dynamics."
            )
        moves.append(move)

    return moves


def generate_inversions(domain: str,
                        demand_pattern: str = "") -> list[dict]:
    """Generate 'flip the perspective' suggestions.

    Instead of serving the obvious customer, serve the other side.
    """
    inversions = []

    if demand_pattern and demand_pattern in INVERSION_MAP:
        inversions.append({
            "pattern": demand_pattern,
            "inversion": INVERSION_MAP[demand_pattern],
            "domain": domain,
            "description": (
                f"In {domain}, everyone is building for the demand side "
                f"({demand_pattern.replace('_', ' ')}). Flip it: "
                f"{INVERSION_MAP[demand_pattern]}."
            ),
            "actions": [
                f"Interview 3 {domain} suppliers/creators about their biggest blind spot",
                "Check if B2B version of this need has higher willingness to pay",
                "Prototype for the supply side using your existing signal data",
            ],
        })
    else:
        # Generic inversions when no demand pattern is known
        for pattern, inv in list(INVERSION_MAP.items())[:2]:
            inversions.append({
                "pattern": pattern,
                "inversion": inv,
                "domain": domain,
                "description": (
                    f"Consider flipping the perspective: {inv}. "
                    f"The supply side in {domain} is often underserved."
                ),
                "actions": [
                    "Research supply-side pain points in this domain",
                    "Check if B2B pricing is viable for this flip",
                ],
            })

    return inversions


def generate_reframe(scores: dict,
                     verdict: str,
                     weakest_dimension: str = "",
                     scoring_details: list | None = None,
                     domain: str = "",
                     demand_pattern: str = "") -> dict:
    """Generate reframing suggestions based on scoring results.

    Args:
        scores: {criterion_id: score} or {dimension_name: {average, ...}}
        verdict: "MAYBE" or "KILL"
        weakest_dimension: name of the weakest scoring dimension
        scoring_details: list of {dimension, criterion, score} from scorer
        domain: opportunity domain (e.g., "health", "devtools")
        demand_pattern: detected demand pattern (e.g., "decision_proxy")

    Returns a dict with reframe suggestions, lateral moves, and inversions.
    """
    suggestions = []

    # Find weak criteria (score <= 4)
    weak_criteria = {}
    if scoring_details:
        for d in scoring_details:
            if d.get("score", 5) <= 4:
                dim = d["dimension"]
                crit = d.get("criterion", "")
                weak_criteria.setdefault(dim, []).append({
                    "criterion": crit,
                    "score": d["score"],
                })

    # Generate suggestions for each weak dimension
    for dim_name, strategies in REFRAME_STRATEGIES.items():
        is_weakest = dim_name == weakest_dimension
        dim_weak = weak_criteria.get(dim_name, [])

        if not dim_weak and not is_weakest:
            continue

        for strategy in strategies:
            # Check if this strategy's trigger criterion is weak
            trigger = strategy.get("if_low", "")
            triggered = any(w["criterion"].lower().replace(" ", "_") == trigger or
                          trigger in w.get("criterion", "").lower()
                          for w in dim_weak)

            if triggered or (is_weakest and not dim_weak):
                suggestions.append({
                    "dimension": dim_name,
                    "strategy": strategy["strategy"],
                    "description": strategy["description"],
                    "actions": strategy["actions"],
                    "triggered_by": trigger,
                    "priority": "high" if is_weakest else "medium",
                })

    # Sort: high priority first
    suggestions.sort(key=lambda s: 0 if s["priority"] == "high" else 1)

    # Overall guidance
    if verdict == "KILL":
        overall = (
            "This opportunity scored below threshold, but KILL doesn't mean the "
            "space is bad — it might mean the current framing is wrong. "
            "Consider the pivots below before moving on."
        )
    else:  # MAYBE
        overall = (
            "This opportunity is borderline. The suggestions below target "
            "your weakest areas. Pick ONE to focus on for the next 2 weeks, "
            "then re-score."
        )

    # Lateral moves and inversions (when domain/demand_pattern available)
    lateral_moves = []
    inversions = []
    if domain:
        lateral_moves = generate_lateral_moves(
            domain, demand_pattern=demand_pattern,
            weakest_dimension=weakest_dimension,
        )
        inversions = generate_inversions(domain, demand_pattern=demand_pattern)

    return {
        "verdict": verdict,
        "overall": overall,
        "suggestions": suggestions,
        "weakest_dimension": weakest_dimension,
        "lateral_moves": lateral_moves,
        "inversions": inversions,
    }


def format_reframe_report(reframe: dict) -> str:
    """Format reframing suggestions as readable report."""
    lines = [
        "# Reframe Suggestions",
        "",
        f"Verdict: **{reframe['verdict']}**",
        f"Weakest: **{reframe['weakest_dimension']}**",
        "",
        reframe["overall"],
        "",
    ]

    for i, s in enumerate(reframe["suggestions"], 1):
        priority_tag = " [HIGH PRIORITY]" if s["priority"] == "high" else ""
        lines.extend([
            f"## {i}. {s['strategy']}{priority_tag}",
            f"*{s['dimension']}*",
            "",
            s["description"],
            "",
            "**Actions:**",
        ])
        for action in s["actions"]:
            lines.append(f"  - {action}")
        lines.append("")

    if not reframe["suggestions"]:
        lines.append("No specific reframe suggestions — the weak scores are in areas that need direct data (interviews, MVT).")

    # Lateral moves
    lateral = reframe.get("lateral_moves", [])
    if lateral:
        lines.extend(["", "## Lateral Moves (Adjacent Domains)", ""])
        for move in lateral[:3]:  # Show top 3
            lines.append(f"- **{move['from_domain']} → {move['to_domain']}**: {move['description']}")
            if move.get("rationale"):
                lines.append(f"  _{move['rationale']}_")
        lines.append("")

    # Inversions
    inversions = reframe.get("inversions", [])
    if inversions:
        lines.extend(["## Perspective Inversions", ""])
        for inv in inversions:
            lines.extend([
                f"**{inv['pattern'].replace('_', ' ').title()}** → {inv['inversion']}",
                "",
                inv["description"],
                "",
            ])
            if inv.get("actions"):
                for action in inv["actions"]:
                    lines.append(f"  - {action}")
            lines.append("")

    return "\n".join(lines)
