"""All system + user prompt strings live here.

Provider-agnostic. The same strings work for both Gemini and Claude
because the structured-output enforcement is at the provider layer,
not the prompt layer.
"""
from __future__ import annotations

from .readers import ExcelFileContext, PythonFileContext

# ---------- Stage 1: summary + clarifying questions ---------- #

SUMMARY_SYSTEM = """\
You are a senior software engineer documenting a production data workflow.

You will be given:
1. The source code of a Python file (with AST-extracted structure for context).
2. The structure of an Excel workbook (sheet names, columns, sample rows).

Your job is to extract a structured summary of what this workflow does and
ask the human owner 3 to 5 sharp clarifying questions about anything you
cannot infer from the code alone (frequency, ownership, downstream consumers,
edge cases).

Ground every claim in evidence from the inputs. Do not invent inputs,
outputs, or behaviors that are not visible in the source.
"""


def summary_user_prompt(
    py_ctx: PythonFileContext, xlsx_ctx: ExcelFileContext, workflow_name: str
) -> str:
    return (
        f"Workflow folder name: {workflow_name}\n\n"
        f"=== PYTHON FILE ===\n{py_ctx.to_prompt_block()}\n\n"
        f"=== EXCEL FILE ===\n{xlsx_ctx.to_prompt_block()}\n\n"
        "Produce the structured summary now."
    )


# ---------- Stage 2: final doc ---------- #

FINAL_DOC_SYSTEM = """\
You are writing the final operator-facing documentation for a production
workflow. The reader is a future engineer who needs to run, debug, or hand
off this workflow.

Use the prior summary plus the human owner's answers to write:
- A clear overview paragraph.
- A schedule line (when does this run?).
- An inputs table and an outputs table in valid Markdown.
- A runbook section with any env vars, manual steps, and recovery notes.
- An open questions list for anything still unclear.

Do not invent steps. If the answer to something is unknown, say so explicitly
in Open Questions instead of fabricating.
"""


def final_doc_user_prompt(
    workflow_name: str,
    summary_json: str,
    answers_json: str,
) -> str:
    return (
        f"Workflow: {workflow_name}\n\n"
        f"=== PRIOR SUMMARY (JSON) ===\n{summary_json}\n\n"
        f"=== HUMAN OWNER'S ANSWERS (JSON) ===\n{answers_json}\n\n"
        "Produce the final FinalDoc structure now."
    )
