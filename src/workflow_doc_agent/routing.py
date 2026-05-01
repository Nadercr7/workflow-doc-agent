"""Model routing: pick a cheap model for simple stages, expensive for the final doc.

Pattern: borrow from cost-aware-llm-pipeline skill. The summary stage
just extracts known fields, so a small/fast model is enough. The final
doc generation needs better long-form writing, so we step up.
"""
from __future__ import annotations

from typing import Literal

Stage = Literal["summary", "questions", "final_doc"]
Provider = Literal["gemini", "claude"]


_ROUTING: dict[tuple[Provider, Stage], str] = {
    # Cheap models for extraction stages
    ("gemini", "summary"): "gemini-2.5-flash",
    ("gemini", "questions"): "gemini-2.5-flash",
    ("claude", "summary"): "claude-haiku-4-5",
    ("claude", "questions"): "claude-haiku-4-5",
    # Step up for the final long-form doc.
    # Note: gemini-2.5-pro has tighter free-tier daily quotas than flash;
    # we keep flash here so the live demo runs reliably on a free key.
    # Bump to "gemini-2.5-pro" once you have a paid key.
    ("gemini", "final_doc"): "gemini-2.5-flash",
    ("claude", "final_doc"): "claude-sonnet-4-5",
}


def select_model(provider: Provider, stage: Stage) -> str:
    """Return the model name for a given provider and stage."""
    try:
        return _ROUTING[(provider, stage)]
    except KeyError as exc:
        raise ValueError(
            f"No model configured for provider={provider} stage={stage}"
        ) from exc
