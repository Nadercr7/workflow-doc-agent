# workflow-doc-agent

A small agent that documents production Python workflows. Point it at a folder
that contains a Python script and an Excel report, answer a few clarifying
questions, and it writes a Markdown runbook.

**Visual walkthrough:** https://nadercr7.github.io/workflow-doc-agent/

Built as a pre-call working prototype for an AI consulting engagement that
needed exactly this loop:

> "Have an agent look at a folder of production work (a Python file and an
> Excel report), summarize the purpose of the code, ask a few questions on
> frequency of the workflow, and then auto-build the documentation for it."

## Why two providers

The agent runs on either **Google Gemini** or **Anthropic Claude** behind a
single `LLMProvider` interface. Same Pydantic schemas, same agent loop, same
output shape. Switching is one env var:

```
LLM_PROVIDER=gemini   # or claude
```

The Gemini path is what's used in the live demo (free key from the developer
console). The Claude path is fully wired and unit-tested with a mocked SDK
client. Drop an `ANTHROPIC_API_KEY` in `.env` and rerun the same command and
the same agent runs against `claude-haiku-4-5` and `claude-sonnet-4-5`.

This is deliberate. Vendor lock-in is a real cost; the abstraction is cheap.

## Quickstart

Requires Python 3.11+. From the repo root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
# edit .env and set GEMINI_API_KEY (free tier works) or ANTHROPIC_API_KEY
```

Generate the included finance sample workbook, then run the agent on it:

```powershell
python samples\revenue_forecast\forecast_pipeline.py
workflow-doc run samples\revenue_forecast --provider gemini --budget 0.50 --non-interactive
```

Output lands at `outputs/revenue_forecast_gemini.md`.

For an interactive run that asks the clarifying questions in the terminal,
drop `--non-interactive`.

## What it does

Three stages, each one validated by a Pydantic model:

1. **Read.** Walk the folder, AST-parse the `.py` file, sample the `.xlsx`
   sheets and headers. No code executed, no full files dumped to the LLM.
2. **Summarize + question.** Cheap model (`gemini-2.5-flash` or
   `claude-haiku-4-5`) emits a `WorkflowSummary` and three to five clarifying
   questions about schedule, owner, downstream consumers.
3. **Document.** Step-up model (`gemini-2.5-pro` or `claude-sonnet-4-5`)
   takes the summary plus your answers and produces a `FinalDoc` with
   Overview, Schedule, Inputs, Outputs, Runbook, and Open Questions.

Every call goes through a `CostTracker` with a hard `--budget` ceiling. If a
run would exceed the budget, the agent stops with `BudgetExceeded` rather
than burn another dollar.

## Repo layout

```
src/workflow_doc_agent/
  schemas.py     # Pydantic models for every output stage
  readers.py     # AST + openpyxl pre-digest, no code execution
  providers.py   # LLMProvider Protocol + Gemini and Claude implementations
  prompts.py     # System and user prompts for each stage
  routing.py     # Per-provider, per-stage model selection
  cost.py        # Frozen-dataclass cost tracker with budget enforcement
  retry.py       # Exponential backoff for transient API errors
  agent.py       # The three-stage agent loop
  cli.py         # Typer entry point
samples/
  revenue_forecast/
    forecast_pipeline.py   # Realistic finance sample (linear trend + sensitivity)
    input_data.csv         # 24 months of fake monthly revenue
evals/
  capability_eval.py       # Pass/fail checks on the generated doc
  regression_eval.py       # Baseline diff
tests/
  test_readers.py
  test_cost_tracker.py
  test_providers.py        # Mocked SDKs, no network
docs/
  architecture.md          # Agent loop, schemas, where this slots in production
  cost-and-evals.md        # CostTracker maths and EDD philosophy
```

## Tests

```powershell
pytest -q
```

Nine tests, none touch the network. The provider tests use `MagicMock` to
prove the parsing logic against a forged tool-use block (Claude) and a forged
JSON response (Gemini).

## License

MIT. See [LICENSE](LICENSE).
