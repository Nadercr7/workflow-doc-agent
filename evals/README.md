# Eval Harness

Tiny, opinionated. Treats agent outputs like code: they must pass tests
before they ship.

Two evals here, runnable with plain `python`.

## capability_eval.py

Pass/fail check that the agent's generated documentation contains every
required section and is non-trivially sized. Run after generating output:

```powershell
workflow-doc run samples/revenue_forecast --non-interactive
python evals/capability_eval.py
```

## regression_eval.py

Compares a fresh run against the committed baseline at
`outputs/revenue_forecast_gemini.md`. Fails if the new output shrinks
below 50% of the baseline or drops a required section. This is the
cheap-and-effective version of an LLM regression test: it catches the
most common failure mode (model degrades and emits a stub).

## Why eval-driven development matters

When Ryan says "many, many more workflows", the question is not "does
the agent work today" but "do we know when it stops working tomorrow".
Evals are the mechanism. Add one eval per real client workflow we
onboard, and the suite becomes a pass/fail CI gate before any prompt or
model change ships.

Pattern reference:
`D:\Personal attachements\Repos\everything-claude-code\skills\eval-harness\SKILL.md`
