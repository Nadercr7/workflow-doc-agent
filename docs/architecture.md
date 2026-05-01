# Architecture

## The loop

```
   folder of work               readers.py
   (.py + .xlsx)   ----->   discover_workflow_files
                            read_python_file (AST)
                            read_excel_file (openpyxl)
                                    |
                                    v
                            PythonFileContext
                            ExcelFileContext
                                    |
                                    v
                          providers.parse(
                            output_format=WorkflowSummary
                          )                          [stage 1, cheap model]
                                    |
                                    v
                            WorkflowSummary
                            + clarifying_questions
                                    |
                                    v
                          collect_answers_*           [human in the loop,
                                    |                  or default skipped]
                                    v
                            WorkflowAnswers
                                    |
                                    v
                          providers.parse(
                            output_format=FinalDoc
                          )                          [stage 2, step-up model]
                                    |
                                    v
                            FinalDoc.to_markdown()
                                    |
                                    v
                            outputs/<name>_<provider>.md
```

Every arrow is typed. Every LLM call returns a validated Pydantic instance
or raises. There is no string parsing of model output anywhere in the agent
code outside the providers themselves.

## Schemas

Defined in `src/workflow_doc_agent/schemas.py`:

| Model              | Stage           | Notes                                       |
|--------------------|-----------------|---------------------------------------------|
| `PythonFileSummary`| internal        | One-line purpose, inputs, outputs, deps     |
| `ExcelFileSummary` | internal        | Sheets, columns, sample-row guesses         |
| `WorkflowSummary`  | stage 1 output  | Includes 3 to 5 `clarifying_questions`      |
| `WorkflowAnswers`  | human input     | One `Answer` per `Question.id`              |
| `FinalDoc`         | stage 2 output  | Has `to_markdown()` for the published file  |

The Pydantic schemas double as JSON schemas:

- **Claude**: Each schema becomes the `input_schema` of a single forced tool
  call (`tool_choice={"type": "tool", "name": tool_name}`). Claude is
  required to call that tool, so the response is structured by construction.
- **Gemini**: Each schema is rendered into the system prompt with
  `response_mime_type="application/json"`, and the result is validated with
  `output_format.model_validate_json(resp.text)`. The Pydantic emitter
  produces extras Gemini's schema validator rejects (`additionalProperties`,
  some `$ref` shapes), so we strip those for the prompt copy and validate
  client-side. Same guarantee, fewer moving parts.

## Provider abstraction

```python
class LLMProvider(Protocol):
    name: str
    def parse(
        self, *, system: str, user: str,
        output_format: Type[T], model: str, max_tokens: int = 2048,
    ) -> tuple[T, CostRecord]: ...
```

Two implementations live side by side. The agent loop never imports
`anthropic` or `google.genai` directly. Adding a third provider (Bedrock,
Vertex, a local Ollama) is one new class, no changes to the agent.

## Where this slots in production

The CLI entry point is the prototype shape. The library shape is what would
ship:

```python
from workflow_doc_agent.agent import run_agent
from workflow_doc_agent.providers import get_provider

provider = get_provider("claude")
result = run_agent(folder=Path("/box/Drive/finance/forecast"),
                  provider=provider,
                  budget_usd=0.20,
                  interactive=False)
publish_to_notion(result.final_doc.to_markdown())
```

Hooks for the actual stack the client described:

- **Dagster** triggers `run_agent` per workflow folder on a schedule.
- **Box / Drive watcher** kicks a fresh run when a `.py` file or `.xlsx`
  changes; the agent's `CostTracker` keeps the spend bounded.
- **Notion / GitHub** receive the rendered Markdown via their own SDKs;
  the agent doesn't know or care about the destination.
- **Logging** is structured stdout (Rich), trivially shippable to whatever
  observability you use.

## Failure modes

- **API transient errors** (timeouts, 5xx, rate-limit): retried with
  exponential backoff in `retry.py`.
- **Budget exceeded**: the next call after the running total clears the
  budget raises `BudgetExceeded`. The current run halts; previous calls'
  output is still on disk in the cost tracker for inspection.
- **Schema mismatch from the model**: `model_validate_json` raises with the
  full validation error, so failures point at the exact field.
- **Code-fenced JSON from Gemini**: stripped automatically before retry.
