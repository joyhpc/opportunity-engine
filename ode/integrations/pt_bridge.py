"""pt bridge — sync opportunities with project-tracker.

Handles:
- Opportunity -> pt project promotion (when graduated)
- Decision syncing
- Status synchronization
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path


PT_DIR = Path.home() / "project-tracker"


def pt_available() -> bool:
    """Check if project-tracker is available."""
    return PT_DIR.exists() and (PT_DIR / "pt").exists()


def pt_command(args: list[str]) -> tuple[int, str]:
    """Run a pt command and return (returncode, output).

    Args should be a list of arguments (no shell injection risk).
    """
    if not pt_available():
        return 1, "project-tracker not found"

    try:
        result = subprocess.run(
            ["python3", "pt"] + args,
            cwd=str(PT_DIR),
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "pt command timed out"
    except Exception as e:
        return 1, str(e)


def sync_decision(decision: str, source: str = "ode", impact: str = "") -> bool:
    """Sync a decision to pt."""
    args = ["decision", "--add", decision, "--source", source]
    if impact:
        args.extend(["--impact", impact])
    code, output = pt_command(args)
    return code == 0


def promote_to_project(opp_name: str, template: str = "opportunity_7stage") -> bool:
    """Promote an opportunity to a pt project using a DAG template."""
    return sync_decision(
        f"Opportunity '{opp_name}' promoted to project",
        source="ode",
        impact="New project created from opportunity assessment",
    )


def get_pt_status() -> dict | None:
    """Get current pt status."""
    code, output = pt_command(["status"])
    if code == 0:
        return {"status": "ok", "output": output}
    return None
