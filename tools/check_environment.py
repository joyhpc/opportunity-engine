#!/usr/bin/env python3
"""Cross-platform environment checks for the import integration path."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures: list[str] = []
    print(f"python={sys.version.split()[0]}")
    print(f"platform={platform.system()} {platform.release()}")
    print(f"repo={ROOT}")

    if sys.version_info < (3, 10):
        failures.append("Python 3.10+ is required")

    for exe in ("git",):
        found = shutil.which(exe)
        print(f"{exe}={found or 'missing'}")
        if not found:
            failures.append(f"{exe} is required")

    for rel in (
        "imports/opportunity-detector/templates/opportunity_detector.yaml",
        "imports/opportunity-detector/subtasks/signal_capture.yaml",
        "examples/import_integration/opportunity_seed.json",
        "examples/profiles/open_founder_profile.json",
        "sources/opportunity_sources.yaml",
    ):
        path = ROOT / rel
        print(f"check={rel} exists={path.exists()}")
        if not path.exists():
            failures.append(f"Missing {rel}")

    try:
        subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True)
    except Exception as exc:  # pragma: no cover - diagnostic path
        failures.append(f"git status failed: {exc}")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}", file=sys.stderr)
        return 1

    print("[OK] environment ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
