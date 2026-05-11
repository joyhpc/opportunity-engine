"""Phrase taxonomy and thresholds for the pain listener."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_REDDIT_SUBS = [
    "SaaS",
    "SideProject",
    "microsaas",
    "startups",
    "Entrepreneur",
    "ProductManagement",
    "webdev",
    "ArtificialIntelligence",
    "LocalLLaMA",
]

DEFAULT_PROFILE_KEYWORDS = [
    "AI agents",
    "developer tools",
    "automation",
    "knowledge systems",
    "vertical SaaS",
    "workflow",
]

GRADE_STRENGTH = {"C": 3, "D": 2, "E": 1}
VALID_EVIDENCE_GRADES = tuple(GRADE_STRENGTH)


@dataclass(frozen=True)
class PainThresholds:
    keep_founder_fit_min: float = 52.0
    keep_priority_min: float = 48.0
    keep_priority_fallback: float = 55.0
    cluster_grade_c_pain_min: float = 75.0
    grade_c_pain_min: float = 65.0
    grade_d_commercial_pain_min: float = 60.0
    validate_now_priority_min: float = 72.0
    validate_now_fit_min: float = 60.0
    research_next_priority_min: float = 60.0


THRESHOLDS = PainThresholds()

COMPLAINT_PHRASES = [
    "pain",
    "painful",
    "problem",
    "struggle",
    "struggling",
    "frustrating",
    "annoying",
    "hate",
    "hard to",
    "too hard",
    "difficult",
    "broken",
    "slow",
    "messy",
    "manual",
    "tedious",
    "repetitive",
    "bottleneck",
    "overwhelming",
    "doesn't work",
    "time consuming",
    "takes too long",
    "waste time",
    "too expensive",
    "expensive",
    "can't",
    "can't find",
    "cannot find",
    "failure",
    "failures",
    "fails",
    "not working",
]

REQUEST_PHRASES = [
    "wish there was",
    "looking for",
    "any tool",
    "need a",
    "need to",
    "need help",
    "is there a",
    "does anyone know",
    "recommend",
    "alternative to",
    "how do i",
    "help with",
]

PAIN_PHRASES = COMPLAINT_PHRASES

BUYER_PHRASES = [
    "pay for",
    "would pay",
    "paid",
    "budget",
    "pricing",
    "subscription",
    "invoice",
    "mrr",
    "arr",
    "revenue",
    "contract",
    "purchase",
    "$",
]

COMMERCIAL_CONTEXT_PHRASES = [
    "customer",
    "client",
    "agency",
    "founder",
    "team",
    "business",
    "b2b",
    "sales",
    "operator",
    "workflow",
]

SUCCESS_STORY_PHRASES = [
    "made my first internet money",
    "couldn't be happier",
    "i made",
    "we made",
    "i built",
    "we built",
    "i launched",
    "we launched",
    "just launched",
    "my saas",
    "our saas",
    "show hn",
]

REQUEST_INTENT_PHRASES = [
    "looking for",
    "need a",
    "need to",
    "need help",
    "any tool",
    "is there a",
    "does anyone know",
    "how do i",
    "wish there was",
    "help with",
]

STRONG_SUCCESS_STORY_PHRASES = [
    "made my first internet money",
    "couldn't be happier",
    "i made",
    "we made",
    "i built",
    "we built",
    "i launched",
    "we launched",
    "just launched",
    "show hn",
]

WORKAROUND_PHRASES = [
    "spreadsheet",
    "notion",
    "zapier",
    "airtable",
    "manual process",
    "copy paste",
    "workaround",
    "script",
    "hack together",
    "glue",
]

URGENCY_PHRASES = [
    "urgent",
    "asap",
    "deadline",
    "blocked",
    "blocking",
    "production",
    "lost",
    "churn",
    "cancel",
]

DOMAIN_SEEDS = {
    "ai_agents": [
        "ai agent",
        "agent",
        "llm",
        "gpt",
        "rag",
        "prompt",
        "chatbot",
        "copilot",
        "autonomous",
    ],
    "developer_tools": [
        "developer",
        "api",
        "sdk",
        "github",
        "code",
        "debug",
        "deploy",
        "devtool",
        "ci",
        "database",
        "observability",
    ],
    "automation": [
        "automation",
        "workflow",
        "zapier",
        "integrate",
        "integration",
        "manual",
        "ops",
    ],
    "knowledge_systems": [
        "knowledge",
        "docs",
        "documentation",
        "wiki",
        "search",
        "notes",
        "retrieval",
    ],
    "vertical_saas": [
        "saas",
        "crm",
        "customer",
        "invoice",
        "booking",
        "clinic",
        "agency",
        "real estate",
        "law firm",
    ],
    "creator_tools": [
        "creator",
        "video",
        "podcast",
        "newsletter",
        "content",
        "social media",
    ],
    "sales_marketing": [
        "lead",
        "sales",
        "email",
        "outreach",
        "campaign",
        "ads",
        "seo",
    ],
    "customer_support": [
        "support",
        "ticket",
        "helpdesk",
        "chat",
        "handoff",
        "routing",
    ],
}
