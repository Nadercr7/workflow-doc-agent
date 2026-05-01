"""Cost tracking with frozen dataclasses (immutable, additive).

Pattern borrowed from the cost-aware-llm-pipeline skill in
D:\\Personal attachements\\Repos\\everything-claude-code\\skills\\.

Why this matters: when Ryan says "many, many more workflows", the
difference between $50/month and $500/month in API spend is a
30-line CostTracker and a routing function.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Approximate per-million-token prices in USD.
# These are intentionally conservative. Real-time pricing can be
# updated in one place if it ever changes.
_PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic (input, output)
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-opus-4-5": (15.00, 75.00),
    # Google
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-flash-latest": (0.30, 2.50),
    "gemini-pro-latest": (1.25, 10.00),
}


@dataclass(frozen=True, slots=True)
class CostRecord:
    """One LLM call's cost, frozen."""

    stage: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

    @classmethod
    def from_usage(
        cls,
        *,
        stage: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> "CostRecord":
        in_price, out_price = _PRICES_USD_PER_MTOK.get(model, (0.0, 0.0))
        cost = (input_tokens * in_price + output_tokens * out_price) / 1_000_000
        return cls(
            stage=stage,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


@dataclass(frozen=True, slots=True)
class CostTracker:
    """Cumulative cost tracker. Add-only, never mutates existing state."""

    budget_limit_usd: float = 0.50
    records: tuple[CostRecord, ...] = field(default_factory=tuple)

    def add(self, record: CostRecord) -> "CostTracker":
        return CostTracker(
            budget_limit_usd=self.budget_limit_usd,
            records=(*self.records, record),
        )

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def total_calls(self) -> int:
        return len(self.records)

    @property
    def over_budget(self) -> bool:
        return self.total_cost_usd > self.budget_limit_usd

    @property
    def headroom_pct(self) -> float:
        if self.budget_limit_usd <= 0:
            return 0.0
        used = self.total_cost_usd / self.budget_limit_usd
        return max(0.0, 1.0 - used) * 100.0

    def summary_line(self) -> str:
        per_model: dict[str, int] = {}
        for r in self.records:
            per_model[r.model] = per_model.get(r.model, 0) + 1
        breakdown = ", ".join(f"{n}x {m}" for m, n in per_model.items())
        return (
            f"Total: ${self.total_cost_usd:.4f} across {self.total_calls} call(s). "
            f"Budget: ${self.budget_limit_usd:.2f}. "
            f"Headroom: {self.headroom_pct:.1f}%. "
            f"({breakdown})"
        )


class BudgetExceeded(RuntimeError):
    """Raised when a planned call would exceed the configured budget."""
