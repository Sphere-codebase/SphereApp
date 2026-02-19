"""Chat orchestrator for LLM + tool loop."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_chat_event
from app.db.id_utils import next_id
from app.db.models import ChatMessage, ChatSession, User
from app.llm.client import ChatCompletionResult, LLMClient, ToolCall
from app.llm.tools import ToolContext, execute_tool, list_tool_schemas
from app.utils.time import utcnow

ROOT_DIR = Path(__file__).resolve().parents[2]
SYSTEM_RULES_PATH = ROOT_DIR / "docs" / "system_rules.md"
DEVELOPER_POLICY_PATH = ROOT_DIR / "docs" / "developer_policy.md"
DEFAULT_SYSTEM_RULES = "You are a helpful assistant."
DEFAULT_DEVELOPER_POLICY = "Follow developer instructions."
logger = logging.getLogger(__name__)


def safe_read(path: Path, default: str) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        logger.warning("Missing prompt file: %s", path)
        return default


@dataclass
class ChatResult:
    session_id: int
    assistant_message: str
    ui_actions: list[dict[str, Any]]
    debug: dict[str, Any] | None
    action_required: bool = False
    proposed_changes: dict[str, Any] | None = None


class ChatOrchestrator:
    def __init__(self, db: Session, user: User, llm_client: LLMClient | None = None) -> None:
        self.db = db
        self.user = user
        self.llm_client = llm_client or LLMClient()

    def run(
        self,
        message: str,
        session_id: int | None,
        *,
        request_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> ChatResult:
        session = self._get_or_create_session(session_id)
        self._store_message(session.id, role="user", content=message)

        messages = self._build_prompt(session.id)
        tools = list_tool_schemas()
        allowed_tools = {tool["function"]["name"] for tool in tools}
        ui_actions: list[dict[str, Any]] = []
        debug: dict[str, Any] = {"tool_steps": 0}

        for step in range(settings.llm_max_steps):
            result = self.llm_client.chat_complete(messages=messages, tools=tools)
            self._store_message(session.id, role="assistant", content=result.assistant_text)

            if not result.tool_calls:
                return ChatResult(
                    session_id=session.id,
                    assistant_message=result.assistant_text,
                    ui_actions=ui_actions,
                    debug=debug if settings.env in {"dev", "test"} else None,
                )

            debug["tool_steps"] = step + 1
            if step == settings.llm_max_steps - 1:
                return ChatResult(
                    session_id=session.id,
                    assistant_message="Reached max tool steps without resolution.",
                    ui_actions=ui_actions,
                    debug=debug if settings.env in {"dev", "test"} else None,
                )

            tool_context = ToolContext(
                db=self.db,
                user_id=self.user.id,
                clinic_id=self.user.clinic_id,
                role=self.user.role,
                chat_session_id=session.id,
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
            )
            messages.append(self._assistant_tool_call_message(result))
            for tool_call in result.tool_calls:
                if tool_call.name not in allowed_tools:
                    logger.warning("Skipping unknown tool call: %s", tool_call.name)
                    continue
                log_chat_event(
                    "tool_call",
                    {
                        "user_id": str(self.user.id),
                        "chat_session_id": str(session.id),
                        "tool_name": tool_call.name,
                        "tool_args": self._summarize_payload(tool_call.arguments),
                    },
                )
                self._store_tool_call(session.id, tool_call)
                try:
                    tool_result = execute_tool(tool_call.name, tool_call.arguments, tool_context)
                except ValidationError as exc:
                    tool_result = {
                        "error": {
                            "code": "TOOL_VALIDATION_ERROR",
                            "message": "Tool arguments invalid",
                            "details": exc.errors(),
                        }
                    }
                self._store_tool_result(session.id, tool_call.name, tool_result)
                log_chat_event(
                    "tool_result",
                    {
                        "user_id": str(self.user.id),
                        "chat_session_id": str(session.id),
                        "tool_name": tool_call.name,
                        "tool_result": self._summarize_payload(tool_result),
                    },
                )
                if tool_call.name == "request_form" and isinstance(tool_result, dict):
                    ui_actions.append(tool_result)
                if isinstance(tool_result, dict) and tool_result.get("action_required"):
                    proposal_payload = {
                        "proposal_id": str(uuid.uuid4()),
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "proposed_changes": tool_result.get("proposed_changes"),
                    }
                    return ChatResult(
                        session_id=session.id,
                        assistant_message="Confirmation required to proceed.",
                        ui_actions=ui_actions,
                        debug=debug if settings.env in {"dev", "test"} else None,
                        action_required=True,
                        proposed_changes=proposal_payload,
                    )
                messages.append(self._tool_result_message(tool_call, tool_result))

        return ChatResult(
            session_id=session.id,
            assistant_message="Unable to complete request.",
            ui_actions=ui_actions,
            debug=debug if settings.env in {"dev", "test"} else None,
        )

    def _get_or_create_session(self, session_id: int | None) -> ChatSession:
        if session_id:
            session = self.db.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.doctor_id == self.user.id,
                    ChatSession.clinic_id == self.user.clinic_id,
                )
            ).scalar_one_or_none()
            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
                )
            return session

        session = ChatSession(
            id=next_id(self.db, ChatSession),
            doctor_id=self.user.id,
            clinic_id=self.user.clinic_id,
            created_at=utcnow(),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def _build_prompt(self, session_id: int) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        messages.append(
            {"role": "system", "content": safe_read(SYSTEM_RULES_PATH, DEFAULT_SYSTEM_RULES)}
        )
        messages.append(
            {
                "role": "system",
                "content": safe_read(DEVELOPER_POLICY_PATH, DEFAULT_DEVELOPER_POLICY),
            }
        )

        history = self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(10)
        ).scalars()
        for item in history:
            if item.role in {"user", "assistant"} and item.content:
                messages.append({"role": item.role, "content": item.content})

        return messages

    def _assistant_tool_call_message(self, result: ChatCompletionResult) -> dict[str, Any]:
        tool_calls = []
        for call in result.tool_calls:
            tool_calls.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
            )
        return {"role": "assistant", "content": result.assistant_text, "tool_calls": tool_calls}

    def _tool_result_message(self, call: ToolCall, tool_result: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": "tool",
            "name": call.name,
            "content": json.dumps(tool_result),
            "tool_call_id": call.id,
        }

    def _store_message(
        self, session_id: int, role: str, content: str | None = None
    ) -> ChatMessage | None:
        if role == "assistant" and (content is None or not content.strip()):
            return None
        message = ChatMessage(
            id=next_id(self.db, ChatMessage),
            session_id=session_id,
            clinic_id=self.user.clinic_id,
            role=role,
            content=content or "",
            created_at=utcnow(),
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def _store_tool_call(self, session_id: int, call: ToolCall) -> None:
        if not call.name:
            return
        rendered = json.dumps(call.arguments, sort_keys=True, default=str)
        content = f"[tool_call] {call.name} args={rendered}"
        message = ChatMessage(
            id=next_id(self.db, ChatMessage),
            session_id=session_id,
            clinic_id=self.user.clinic_id,
            role="assistant",
            content=content,
            created_at=utcnow(),
        )
        self.db.add(message)
        self.db.commit()

    def _store_tool_result(self, session_id: int, tool_name: str, result: dict[str, Any]) -> None:
        if not tool_name or result is None:
            return
        rendered = json.dumps(result, sort_keys=True, default=str)
        content = f"[tool_result] {tool_name} result={rendered}"
        message = ChatMessage(
            id=next_id(self.db, ChatMessage),
            session_id=session_id,
            clinic_id=self.user.clinic_id,
            role="tool",
            content=content,
            created_at=utcnow(),
        )
        self.db.add(message)
        self.db.commit()

    def _summarize_payload(self, payload: dict[str, Any]) -> str:
        try:
            rendered = json.dumps(payload, default=str)
        except TypeError:
            rendered = str(payload)
        if len(rendered) <= settings.max_context_chars:
            return rendered
        return f"{rendered[: settings.max_context_chars]}…"
