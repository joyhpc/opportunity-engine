"""ODE constants: stages, thresholds, schema version."""

SCHEMA_VERSION = "1.0"

# Pipeline stages in order
STAGES = ["SENSE", "SCREEN", "ANALYZE", "VALIDATE", "PLAN", "LAUNCH", "MONITOR"]

# Stage gate thresholds
GATE_THRESHOLDS = {
    "SENSE": {
        "min_strong_signals": 3,
        "description": "≥3 strong signals to enter SCREEN",
    },
    "SCREEN": {
        "go": 70,
        "maybe": 50,
        "kill": 50,
        "description": "≥70 GO, 50-69 MAYBE, <50 KILL",
    },
    "ANALYZE": {
        "npv_positive": True,
        "no_p0_regulatory": True,
        "description": "NPV>0 and no P0 regulatory risk",
    },
}

# Opportunity status values
STATUS_ACTIVE = "active"
STATUS_ON_HOLD = "on_hold"
STATUS_KILLED = "killed"
STATUS_GRADUATED = "graduated"  # promoted to pt project

# Scoring dimensions
SCORING_DIMENSIONS = [
    "market_size",
    "competition",
    "timing",
    "team_fit",
    "economics",
    "ai_native",
]

# Signal strength levels
SIGNAL_STRENGTH = {"强": 3, "中": 2, "弱": 1}

# Default TTL for signals (days)
DEFAULT_SIGNAL_TTL = 30

# Financial model defaults
DEFAULT_CHURN_RATE = 5.0  # monthly %
DEFAULT_DISCOUNT_RATE = 12.0  # annual %

# Data directories (relative to project root)
DATA_DIR = "data"
OPPORTUNITIES_DIR = f"{DATA_DIR}/opportunities"
SIGNALS_DIR = f"{DATA_DIR}/signals"
COMPETITORS_DIR = f"{DATA_DIR}/competitors"
REPORTS_DIR = f"{DATA_DIR}/reports"
EVIDENCE_DIR = f"{DATA_DIR}/evidence"
ALERTS_DIR = f"{DATA_DIR}/alerts"
