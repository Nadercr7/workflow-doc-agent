"""Capability eval: does the agent produce a complete, schema-valid doc?

Pattern from D:\\Personal attachements\\Repos\\everything-claude-code\\skills\\eval-harness.

Run: `python evals/capability_eval.py`
Exit 0 = PASS, 1 = FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE_OUTPUT = REPO / "outputs" / "revenue_forecast_gemini.md"


CHECKS = [
    ("File exists", lambda md: SAMPLE_OUTPUT.exists()),
    ("Has H1 title", lambda md: md.lstrip().startswith("# ")),
    ("Has Overview section", lambda md: "## Overview" in md),
    ("Has Schedule section", lambda md: "## Schedule" in md),
    ("Has Inputs table", lambda md: "## Inputs" in md and "|" in md.split("## Inputs", 1)[1]),
    ("Has Outputs table", lambda md: "## Outputs" in md and "|" in md.split("## Outputs", 1)[1]),
    ("Has Runbook", lambda md: "## Runbook" in md),
    ("Has Open Questions", lambda md: "## Open Questions" in md),
    ("Non-trivial length (>= 600 chars)", lambda md: len(md) >= 600),
]


def main() -> int:
    if not SAMPLE_OUTPUT.exists():
        print(f"FAIL: missing {SAMPLE_OUTPUT}")
        print("Hint: run `workflow-doc run samples/revenue_forecast --non-interactive` first.")
        return 1

    md = SAMPLE_OUTPUT.read_text(encoding="utf-8")
    failed = 0
    for name, check in CHECKS:
        ok = bool(check(md))
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {name}")
        if not ok:
            failed += 1

    print()
    if failed == 0:
        print(f"capability_eval: PASS ({len(CHECKS)}/{len(CHECKS)})")
        return 0
    print(f"capability_eval: FAIL ({len(CHECKS) - failed}/{len(CHECKS)})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
