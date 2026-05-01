"""LLM provider abstraction. Same interface, two implementations.

This is the core trick of the project. The agent calls
`provider.parse(system, user, output_format=Schema)` and gets back a
validated Pydantic instance, no matter which LLM is behind the curtain.

The same pattern powers Wadjet's multi-provider AI fallback (Gemini,
Cloudflare Workers AI). It also makes vendor lock-in a non-issue: the
day Anthropic raises prices or Google ships a new model, we change one
env var.
"""
from __future__ import annotations

import json
import os
from typing import Protocol, Type, TypeVar, runtime_checkable

from pydantic import BaseModel

from .cost import CostRecord
from .retry import call_with_retry

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """Common interface every provider must satisfy."""

    name: str

    def parse(
        self,
        *,
        system: str,
        user: str,
        output_format: Type[T],
        model: str,
        max_tokens: int = 2048,
    ) -> tuple[T, CostRecord]:
        """Return (parsed_output, cost_record)."""
        ...


# ---------- Gemini ---------- #


class GeminiProvider:
    """Provider backed by `google-genai`. Live, used for the demo run."""

    name = "gemini"

    def __init__(self, api_key: str | None = None) -> None:
        from google import genai  # lazy import so users without the SDK can still test the rest

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. See .env.example."
            )
        self._client = genai.Client(api_key=key)

    def parse(
        self,
        *,
        system: str,
        user: str,
        output_format: Type[T],
        model: str,
        max_tokens: int = 2048,
    ) -> tuple[T, CostRecord]:
        from google.genai import types as gtypes

        # We could pass `response_schema=output_format` here, but Gemini's
        # schema validator is stricter than Pydantic's emitter (it rejects
        # `additionalProperties`, some `$ref` shapes, etc.). It's simpler
        # and equally safe to ask for JSON, then validate with Pydantic
        # client-side. Same behavioural guarantee, fewer moving parts.
        schema_hint = json.dumps(_gemini_safe_schema(output_format), indent=2)
        full_system = (
            f"{system}\n\n"
            f"Return JSON that matches this schema exactly. No prose, no markdown fences:\n"
            f"{schema_hint}"
        )

        def _call():
            return self._client.models.generate_content(
                model=model,
                contents=user,
                config=gtypes.GenerateContentConfig(
                    system_instruction=full_system,
                    response_mime_type="application/json",
                    max_output_tokens=max_tokens,
                    temperature=0.2,
                ),
            )

        resp = call_with_retry(_call)
        text = resp.text or ""

        try:
            parsed = output_format.model_validate_json(text)
        except Exception:
            # Sometimes the model wraps JSON in fences. Strip and retry once.
            cleaned = _strip_code_fences(text)
            parsed = output_format.model_validate_json(cleaned)

        usage = getattr(resp, "usage_metadata", None)
        in_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        out_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        cost = CostRecord.from_usage(
            stage="(set by caller)",
            model=model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )
        return parsed, cost


# ---------- Claude ---------- #


class ClaudeProvider:
    """Provider backed by `anthropic`. Drop-in swap for the Gemini path."""

    name = "claude"

    def __init__(self, api_key: str | None = None) -> None:
        from anthropic import Anthropic  # lazy import

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. See .env.example."
            )
        self._client = Anthropic(api_key=key)

    def parse(
        self,
        *,
        system: str,
        user: str,
        output_format: Type[T],
        model: str,
        max_tokens: int = 2048,
    ) -> tuple[T, CostRecord]:
        # We use a single tool with the Pydantic schema as input_schema so
        # Claude is forced to return validated structured JSON. This works
        # across all current Claude models without depending on any
        # `messages.parse` beta endpoint.
        schema = output_format.model_json_schema()
        tool_name = "emit_" + output_format.__name__.lower()

        def _call():
            return self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=[
                    {
                        "name": tool_name,
                        "description": (
                            f"Emit a {output_format.__name__} object. "
                            "All fields must be filled."
                        ),
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user}],
            )

        resp = call_with_retry(_call)

        tool_input: dict | None = None
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                tool_input = block.input
                break
        if tool_input is None:
            raise RuntimeError(
                f"Claude did not call the {tool_name} tool. "
                f"Response: {resp.content!r}"
            )

        parsed = output_format.model_validate(tool_input)

        usage = getattr(resp, "usage", None)
        in_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        out_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cost = CostRecord.from_usage(
            stage="(set by caller)",
            model=model,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )
        return parsed, cost


# ---------- factory ---------- #


def get_provider(name: str | None = None) -> LLMProvider:
    """Return a provider by name. Defaults to LLM_PROVIDER env var, then 'gemini'."""
    name = (name or os.environ.get("LLM_PROVIDER") or "gemini").lower().strip()
    if name == "gemini":
        return GeminiProvider()
    if name == "claude":
        return ClaudeProvider()
    raise ValueError(f"Unknown provider: {name!r}. Use 'gemini' or 'claude'.")


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        # remove first fence line
        s = s.split("\n", 1)[1] if "\n" in s else s
        # remove trailing fence
        if s.rstrip().endswith("```"):
            s = s.rstrip()[: -3].rstrip()
    return s


def _gemini_safe_schema(model_cls: Type[BaseModel]) -> dict:
    """Convert a Pydantic v2 model into a Gemini-compatible JSON schema.

    Gemini rejects `additionalProperties`, `$defs`, and `$ref`. We inline
    refs and drop the unsupported keys so the same Pydantic models can
    drive both providers.
    """
    raw = model_cls.model_json_schema()
    defs = raw.pop("$defs", {})

    def _resolve(node: object) -> object:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                target = defs.get(ref.split("/")[-1])
                if target is not None:
                    return _resolve(json.loads(json.dumps(target)))
            cleaned: dict = {}
            for k, v in node.items():
                if k in {"additionalProperties", "title", "$defs", "$ref"}:
                    continue
                cleaned[k] = _resolve(v)
            return cleaned
        if isinstance(node, list):
            return [_resolve(x) for x in node]
        return node

    return _resolve(raw)  # type: ignore[return-value]


# Re-export json so tests can stub it without polluting top-level imports.
__all__ = [
    "ClaudeProvider",
    "GeminiProvider",
    "LLMProvider",
    "get_provider",
    "json",
]
