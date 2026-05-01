"""Agent orchestrator. Read -> summarize -> ask -> write doc.

All cost-tracked, all routed by stage, all validated at the schema layer.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from rich.console import Console

from .cost import BudgetExceeded, CostRecord, CostTracker
from .prompts import (
    FINAL_DOC_SYSTEM,
    SUMMARY_SYSTEM,
    final_doc_user_prompt,
    summary_user_prompt,
)
from .providers import LLMProvider
from .readers import (
    ExcelFileContext,
    PythonFileContext,
    discover_workflow_files,
    read_excel_file,
    read_python_file,
)
from .routing import select_model
from .schemas import FinalDoc, WorkflowAnswers, WorkflowSummary


console = Console()


@dataclass(frozen=True, slots=True)
class AgentResult:
    summary: WorkflowSummary
    answers: WorkflowAnswers
    doc: FinalDoc
    output_path: Path
    cost: CostTracker


def _enforce_budget(cost: CostTracker) -> None:
    if cost.over_budget:
        raise BudgetExceeded(
            f"Run halted: ${cost.total_cost_usd:.4f} exceeds budget "
            f"${cost.budget_limit_usd:.2f}."
        )


def run_summary_stage(
    provider: LLMProvider,
    py_ctx: PythonFileContext,
    xlsx_ctx: ExcelFileContext,
    workflow_name: str,
    cost: CostTracker,
) -> tuple[WorkflowSummary, CostTracker]:
    model = select_model(provider.name, "summary")
    console.print(f"[dim][1/3] Summarizing with {model}...[/dim]")
    summary, record = provider.parse(
        system=SUMMARY_SYSTEM,
        user=summary_user_prompt(py_ctx, xlsx_ctx, workflow_name),
        output_format=WorkflowSummary,
        model=model,
        max_tokens=4096,
    )
    record = replace(record, stage="summary")
    cost = cost.add(record)
    _enforce_budget(cost)
    return summary, cost


def collect_answers_interactive(summary: WorkflowSummary) -> WorkflowAnswers:
    """Prompt the human for answers to the LLM's clarifying questions."""
    console.print()
    console.print(f"[bold cyan][2/3] Clarifying questions for: {summary.workflow_name}[/bold cyan]")
    extra: dict[str, str] = {}
    for i, q in enumerate(summary.clarifying_questions, start=1):
        console.print(f"\n[bold]Q{i}.[/bold] {q}")
        ans = console.input("[green]> [/green]").strip()
        extra[f"q{i}"] = ans

    # Pull frequency / owner / consumers out of free-text answers heuristically.
    freq = "monthly"
    for ans in extra.values():
        low = ans.lower()
        for f in ("daily", "weekly", "monthly", "quarterly", "ad_hoc", "ad hoc"):
            if f in low:
                freq = "ad_hoc" if "ad" in f else f
                break
    return WorkflowAnswers(
        frequency=freq,  # type: ignore[arg-type]
        owner=extra.get("q1", "Unknown") or "Unknown",
        downstream_consumers=[],
        extra_answers=extra,
    )


def collect_answers_default(summary: WorkflowSummary) -> WorkflowAnswers:
    """Non-interactive defaults so the agent can run end-to-end in CI."""
    return WorkflowAnswers(
        frequency="monthly",
        owner="Finance Ops",
        downstream_consumers=["CFO weekly review"],
        extra_answers={
            f"q{i}": "(default answer for non-interactive run)"
            for i in range(1, len(summary.clarifying_questions) + 1)
        },
    )


def run_final_doc_stage(
    provider: LLMProvider,
    summary: WorkflowSummary,
    answers: WorkflowAnswers,
    cost: CostTracker,
) -> tuple[FinalDoc, CostTracker]:
    model = select_model(provider.name, "final_doc")
    console.print(f"[dim][3/3] Generating doc with {model}...[/dim]")
    doc, record = provider.parse(
        system=FINAL_DOC_SYSTEM,
        user=final_doc_user_prompt(
            workflow_name=summary.workflow_name,
            summary_json=summary.model_dump_json(indent=2),
            answers_json=answers.model_dump_json(indent=2),
        ),
        output_format=FinalDoc,
        model=model,
        max_tokens=3072,
    )
    record = replace(record, stage="final_doc")
    cost = cost.add(record)
    _enforce_budget(cost)
    return doc, cost


def run_agent(
    folder: Path,
    *,
    provider: LLMProvider,
    budget_usd: float = 0.50,
    interactive: bool = True,
    output_dir: Path | None = None,
) -> AgentResult:
    """Run the full agent loop on a workflow folder."""
    folder = folder.resolve()
    py_files, xlsx_files = discover_workflow_files(folder)
    if not py_files:
        raise FileNotFoundError(f"No .py files found in {folder}")
    if not xlsx_files:
        raise FileNotFoundError(f"No .xlsx files found in {folder}")
    py_ctx = read_python_file(py_files[0])
    xlsx_ctx = read_excel_file(xlsx_files[0])

    workflow_name = folder.name
    cost = CostTracker(budget_limit_usd=budget_usd)

    summary, cost = run_summary_stage(provider, py_ctx, xlsx_ctx, workflow_name, cost)
    answers = (
        collect_answers_interactive(summary)
        if interactive
        else collect_answers_default(summary)
    )
    doc, cost = run_final_doc_stage(provider, summary, answers, cost)

    out_dir = output_dir or (folder.parent.parent / "outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{workflow_name}_{provider.name}.md"
    out_path.write_text(doc.to_markdown(), encoding="utf-8")

    console.print()
    console.print(f"[bold green]Wrote:[/bold green] {out_path}")
    console.print(f"[bold]{cost.summary_line()}[/bold]")
    return AgentResult(
        summary=summary,
        answers=answers,
        doc=doc,
        output_path=out_path,
        cost=cost,
    )
