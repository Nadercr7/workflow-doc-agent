# Cost and evals

## Why a CostTracker exists

If this agent runs on every workflow folder in a Box drive, the spend grows
linearly with the catalog. At a few thousand workflows that's enough to
matter. The pattern here is the one the client used to describe their work:
"many, many more workflows."

The tracker is a frozen dataclass:

```python
@dataclass(frozen=True)
class CostTracker:
    budget_limit_usd: float
    records: tuple[CostRecord, ...] = ()

    def add(self, record: CostRecord) -> "CostTracker":
        return CostTracker(self.budget_limit_usd, self.records + (record,))
```

Every `add` returns a new tracker. Nothing mutates. That gives you a clean
audit trail of every call, model, stage, token count, and dollar amount for
free, with no logging glue.

## Pricing table

`cost.py` carries a small dict of public per-million-token prices for the
models we actually call. For example:

| Model               | Input ($/Mtok) | Output ($/Mtok) |
|---------------------|----------------|-----------------|
| `claude-haiku-4-5`  | 1.00           | 5.00            |
| `claude-sonnet-4-5` | 3.00           | 15.00           |
| `gemini-2.5-flash`  | 0.30           | 2.50            |
| `gemini-2.5-pro`    | 1.25           | 10.00           |

Update those numbers when prices change. The tracker math is one-liner from
the pricing table, so the cost of being wrong is bounded to the per-call
estimate, not the total run.

## Budget enforcement

The CLI takes `--budget`, default 0.50 USD. After every parse call:

```python
if cost.over_budget:
    raise BudgetExceeded(cost.summary_line())
```

A run that would have cost $1.20 stops at the first call after the limit,
not after burning all $1.20.

## Routing

`routing.py` keeps a small dict of `(provider, stage) -> model`. Cheap
extraction stages run on Haiku/Flash; the long-form final-doc stage
optionally steps up to Sonnet/Pro.

This is how you scale the same loop across thousands of folders without the
bill spiraling. Most workflows only need the cheap path; the routing makes
the upgrade explicit and one-line revertible.

## Eval-driven development

The `evals/` folder is the smoke test for whether the prompt changes broke
something:

- **`capability_eval.py`** runs a set of pass/fail checks on the generated
  Markdown: file exists, has the H1 title, every required section is
  present, length is non-trivial. Nine checks, currently 9/9 PASS on the
  finance sample.

- **`regression_eval.py`** diffs the latest output against a checked-in
  baseline. Today this is a placeholder that compares baseline against
  itself. In a real CI integration it gates merges: if the prompt change
  drops a Pydantic field from the final doc or rewrites it into something
  shorter and worse, the diff fails.

The pattern is borrowed from the `eval-harness` skill. Two things matter:

1. Evals run after every prompt change, automatically.
2. They report PASS/FAIL on stdout so a CI runner can gate on exit code.

That's it. The point isn't to score the model on a benchmark; it's to know
within seconds whether a prompt edit just broke the contract that downstream
systems rely on.

## What good looks like

A live run on the finance sample:

```
[1/3] Summarizing with gemini-2.5-flash...
[3/3] Generating doc with gemini-2.5-flash...

Wrote: outputs/revenue_forecast_gemini.md
Total: $0.0048 across 2 call(s). Budget: $0.50. Headroom: 99.0%.
capability_eval: PASS (9/9)
```

Half a cent per workflow. At 5,000 workflows a month, the unit economics are
$25/month of LLM spend for a job that would otherwise sit on someone's
to-do list forever.
