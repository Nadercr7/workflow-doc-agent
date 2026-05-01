"""Tests for cost tracking. No LLM, no network."""
from workflow_doc_agent.cost import CostRecord, CostTracker


def test_cost_record_haiku_pricing() -> None:
    r = CostRecord.from_usage(
        stage="summary",
        model="claude-haiku-4-5",
        input_tokens=1_000,
        output_tokens=500,
    )
    # 1k * $1/M + 500 * $5/M = 0.001 + 0.0025 = 0.0035
    assert abs(r.cost_usd - 0.0035) < 1e-9


def test_tracker_is_immutable() -> None:
    t1 = CostTracker(budget_limit_usd=0.10)
    r = CostRecord.from_usage(
        stage="summary", model="gemini-2.5-flash", input_tokens=100, output_tokens=50
    )
    t2 = t1.add(r)
    # Original tracker is untouched.
    assert t1.total_calls == 0
    assert t2.total_calls == 1
    assert t1 is not t2


def test_over_budget_flag() -> None:
    t = CostTracker(budget_limit_usd=0.0001)
    r = CostRecord.from_usage(
        stage="summary",
        model="claude-sonnet-4-5",
        input_tokens=10_000,
        output_tokens=10_000,
    )
    t = t.add(r)
    assert t.over_budget is True
    assert t.headroom_pct == 0.0


def test_summary_line_formats() -> None:
    t = CostTracker(budget_limit_usd=0.50)
    r = CostRecord.from_usage(
        stage="summary", model="gemini-2.5-flash", input_tokens=100, output_tokens=50
    )
    t = t.add(r)
    line = t.summary_line()
    assert "Total: $" in line
    assert "1 call" in line
    assert "gemini-2.5-flash" in line
