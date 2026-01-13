"""LLM client for LM Studio (OpenAI-compatible)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class LLMUnavailable(RuntimeError):
    """Raised when LLM is unreachable or times out."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatCompletionResult:
    assistant_text: str
    tool_calls: list[ToolCall]


class LLMClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.lmstudio_base_url,
            timeout=httpx.Timeout(settings.llm_timeout_seconds),
        )

    @retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3))
    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise LLMUnavailable("LLM request failed") from exc

    def chat_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> ChatCompletionResult:
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
        }
        if tools:
            payload["tools"] = tools

        data = self._post(payload)
        message = data.get("choices", [{}])[0].get("message", {})
        assistant_text = message.get("content") or ""
        tool_calls = []

        for call in message.get("tool_calls", []) or []:
            function = call.get("function", {})
            raw_args = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=call.get("id", ""),
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )

        return ChatCompletionResult(assistant_text=assistant_text, tool_calls=tool_calls)

    def health_check(self) -> None:
        try:
            response = self._client.get("/models")
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise LLMUnavailable("LLM health check failed") from exc
