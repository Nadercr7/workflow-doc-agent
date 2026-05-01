"""Provider tests. We mock the SDK clients so no network calls happen.

The point here is to prove the provider abstraction and Pydantic
contract are wired correctly, so swapping providers is a real
engineering claim, not aspirational.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from workflow_doc_agent.providers import ClaudeProvider, GeminiProvider
from workflow_doc_agent.schemas import PythonFileSummary


def test_claude_provider_parses_tool_use(monkeypatch: pytest.MonkeyPatch) -> None:
    # Build a mock anthropic client.
    fake_client = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.name = "emit_pythonfilesummary"
    fake_block.input = {
        "one_line_purpose": "Compute revenue forecast.",
        "inputs": ["input_data.csv"],
        "outputs": ["monthly_revenue.xlsx"],
        "dependencies": ["openpyxl"],
        "notable_functions": ["main"],
    }
    fake_resp = MagicMock()
    fake_resp.content = [fake_block]
    fake_resp.usage.input_tokens = 100
    fake_resp.usage.output_tokens = 50
    fake_client.messages.create.return_value = fake_resp

    p = ClaudeProvider.__new__(ClaudeProvider)
    p._client = fake_client  # type: ignore[attr-defined]
    parsed, cost = p.parse(
        system="sys",
        user="user",
        output_format=PythonFileSummary,
        model="claude-haiku-4-5",
        max_tokens=512,
    )
    assert isinstance(parsed, PythonFileSummary)
    assert parsed.one_line_purpose == "Compute revenue forecast."
    assert cost.model == "claude-haiku-4-5"
    assert cost.input_tokens == 100
    assert cost.output_tokens == 50


def test_gemini_provider_parses_response_schema() -> None:
    """Test the Gemini path with a mock client. Uses the real google.genai
    types module so the SDK's own imports keep working."""
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.text = (
        '{"one_line_purpose": "Compute forecast.", '
        '"inputs": ["input_data.csv"], '
        '"outputs": ["monthly_revenue.xlsx"], '
        '"dependencies": ["openpyxl"], '
        '"notable_functions": ["main"]}'
    )
    fake_resp.parsed = None
    fake_resp.usage_metadata.prompt_token_count = 200
    fake_resp.usage_metadata.candidates_token_count = 80
    fake_client.models.generate_content.return_value = fake_resp

    p = GeminiProvider.__new__(GeminiProvider)
    p._client = fake_client  # type: ignore[attr-defined]
    parsed, cost = p.parse(
        system="sys",
        user="user",
        output_format=PythonFileSummary,
        model="gemini-2.5-flash",
        max_tokens=512,
    )
    assert isinstance(parsed, PythonFileSummary)
    assert parsed.outputs == ["monthly_revenue.xlsx"]
    assert cost.model == "gemini-2.5-flash"
    assert cost.input_tokens == 200
    assert cost.output_tokens == 80
