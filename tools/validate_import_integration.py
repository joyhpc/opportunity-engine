#!/usr/bin/env python3
"""Validate and optionally write the opportunity-detector import plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ode.imports.detector_integration import build_closed_loop_plan, load_seed, validate_plan


DEFAULT_SEED = ROOT / "examples" / "import_integration" / "opportunity_seed.json"
DEFAULT_OUTPUT = ROOT / "examples" / "import_integration" / "closed_loop_plan.golden.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate imported opportunity-detector integration")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true", help="Write the deterministic golden plan")
    args = parser.parse_args()

    seed = load_seed(args.seed)
    plan = build_closed_loop_plan(seed, ROOT)
    errors = validate_plan(plan)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 1

    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] wrote {args.output.relative_to(ROOT).as_posix()}")
    elif args.output.exists():
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        if expected != plan:
            print("[FAIL] golden plan is out of date; run with --write", file=sys.stderr)
            return 1

    print("[OK] opportunity import integration is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
