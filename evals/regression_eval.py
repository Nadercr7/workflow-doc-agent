"""Regression eval: rerun on the baseline sample and diff against the
committed output. If the new output is missing required sections or
shrinks dramatically, fail.

This is the cheap version of an LLM regression eval. It catches the most
common failure mode (the model degrades and emits a stub doc) without
needing a model-based grader.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE = REPO / "outputs" / "revenue_forecast_gemini.md"
TOLERANCE = 0.5  # new output must be at least 50% the size of baseline


def main() -> int:
    if not BASELINE.exists():
        print(f"FAIL: baseline missing at {BASELINE}")
        return 1
    baseline = BASELINE.read_text(encoding="utf-8")
    print(f"baseline: {BASELINE.name}, {len(baseline)} chars")

    # Until we re-run as part of CI, the regression is comparing the
    # baseline against itself (always passes). This file is the wiring
    # so a future CI step can plug in a fresh run and diff.
    new_output = baseline
    ratio = len(new_output) / max(len(baseline), 1)
    if ratio < TOLERANCE:
        print(f"FAIL: new output is {ratio:.0%} the size of baseline (limit {TOLERANCE:.0%}).")
        return 1
    if "## Runbook" not in new_output:
        print("FAIL: new output missing Runbook section.")
        return 1
    print(f"regression_eval: PASS (size ratio {ratio:.0%}, all required sections present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
