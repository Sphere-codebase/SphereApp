"""LLM client for LM Studio (OpenAI-compatible)."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when LLM is unreachable or times out."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.retryable = retryable


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
    _max_attempts = 3

    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.lmstudio_base_url,
            timeout=httpx.Timeout(settings.llm_timeout_seconds),
        )

    def _redact_text(self, value: str) -> str:
        redacted = value
        patterns = [
            r"(password)\s*[:=]\s*[^\s]+",
            r"(token)\s*[:=]\s*[^\s]+",
            r"(authorization)\s*[:=]\s*[^\s]+",
            r"(jwt)\s*[:=]\s*[^\s]+",
            r"(access_token)\s*[:=]\s*[^\s]+",
        ]
        for pattern in patterns:
            redacted = re.sub(pattern, r"\1=[redacted]", redacted, flags=re.IGNORECASE)
        return redacted

    def _truncate(self, value: str, limit: int = 2000) -> str:
        if len(value) <= limit:
            return value
        return f"{value[:limit]}…"

    def _payload_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages", [])
        summary_messages: list[dict[str, Any]] = []
        if isinstance(messages, list):
            for message in messages[-4:]:
                if not isinstance(message, dict):
                    summary_messages.append({"type": type(message).__name__})
                    continue
                content = message.get("content")
                if isinstance(content, str):
                    content_preview = self._truncate(self._redact_text(content), limit=200)
                elif content is None:
                    content_preview = None
                else:
                    content_preview = f"<{type(content).__name__}>"
                summary_messages.append(
                    {
                        "role": message.get("role"),
                        "content_preview": content_preview,
                        "tool_calls": len(message.get("tool_calls") or []),
                        "has_tool_call_id": bool(message.get("tool_call_id")),
                    }
                )
        return {
            "model": payload.get("model"),
            "temperature": payload.get("temperature"),
            "message_count": len(messages) if isinstance(messages, list) else None,
            "tool_count": len(payload.get("tools") or []),
            "tail_messages": summary_messages,
        }

    def _log_http_failure(
        self,
        response: httpx.Response,
        payload: dict[str, Any],
        *,
        attempt: int,
        retryable: bool,
    ) -> str:
        response_text = self._truncate(self._redact_text(response.text))
        logger.warning(
            "llm request failed status=%s retryable=%s attempt=%s payload_summary=%s body=%s",
            response.status_code,
            retryable,
            attempt,
            self._payload_summary(payload),
            response_text,
        )
        return response_text

    def _extract_text_content(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            return "\n".join(part for part in parts if part).strip()
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
        return str(content)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: LLMUnavailable | None = None
        for attempt in range(1, self._max_attempts + 1):
            started = time.monotonic()
            try:
                response = self._client.post("/chat/completions", json=payload)
            except httpx.RequestError as exc:
                logger.warning(
                    "llm request transport failure "
                    "retryable=%s attempt=%s error=%s payload_summary=%s",
                    True,
                    attempt,
                    exc,
                    self._payload_summary(payload),
                )
                last_error = LLMUnavailable("LLM request failed", retryable=True)
                if attempt == self._max_attempts:
                    raise last_error from exc
                time.sleep(min(2 ** (attempt - 1), 10))
                continue

            if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
                response_text = self._log_http_failure(
                    response,
                    payload,
                    attempt=attempt,
                    retryable=True,
                )
                last_error = LLMUnavailable(
                    f"LLM request failed with HTTP {response.status_code}",
                    status_code=response.status_code,
                    response_text=response_text,
                    retryable=True,
                )
                if attempt == self._max_attempts:
                    raise last_error
                time.sleep(min(2 ** (attempt - 1), 10))
                continue

            if response.is_error:
                response_text = self._log_http_failure(
                    response,
                    payload,
                    attempt=attempt,
                    retryable=False,
                )
                raise LLMUnavailable(
                    f"LLM request failed with HTTP {response.status_code}",
                    status_code=response.status_code,
                    response_text=response_text,
                    retryable=False,
                )

            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                response_text = self._truncate(self._redact_text(response.text))
                logger.warning(
                    "llm returned invalid json payload_summary=%s body=%s",
                    self._payload_summary(payload),
                    response_text,
                )
                raise LLMUnavailable(
                    "LLM returned invalid JSON",
                    status_code=response.status_code,
                    response_text=response_text,
                    retryable=False,
                ) from exc

            if not isinstance(data, dict):
                logger.warning(
                    "llm returned non-object json payload_summary=%s body_type=%s",
                    self._payload_summary(payload),
                    type(data).__name__,
                )
                raise LLMUnavailable(
                    "LLM returned malformed JSON payload",
                    status_code=response.status_code,
                    retryable=False,
                )
            logger.info(
                "llm_http_round status=%s attempt=%s duration_ms=%s",
                response.status_code,
                attempt,
                round((time.monotonic() - started) * 1000, 2),
            )
            return cast(dict[str, Any], data)

        raise last_error or LLMUnavailable("LLM request failed", retryable=True)

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
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            logger.warning(
                "llm response missing choices payload_summary=%s response=%s",
                self._payload_summary(payload),
                self._truncate(self._redact_text(json.dumps(data, default=str))),
            )
            raise LLMUnavailable("LLM response missing choices", retryable=False)

        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            logger.warning(
                "llm response missing message payload_summary=%s response=%s",
                self._payload_summary(payload),
                self._truncate(self._redact_text(json.dumps(data, default=str))),
            )
            raise LLMUnavailable("LLM response missing message", retryable=False)

        assistant_text = self._extract_text_content(message.get("content"))
        tool_calls = []

        for call in message.get("tool_calls", []) or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function", {})
            raw_args = function.get("arguments") if isinstance(function, dict) else "{}"
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    arguments = {}
            elif isinstance(raw_args, dict):
                arguments = raw_args
            else:
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
