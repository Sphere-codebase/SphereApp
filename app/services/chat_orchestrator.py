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
from app.db.models import ChatMessage, ChatSession, Claim, Patient, User
from app.llm.client import ChatCompletionResult, LLMClient, ToolCall
from app.llm.tools import ToolContext, execute_tool, list_tool_schemas

ROOT_DIR = Path(__file__).resolve().parents[2]
SYSTEM_RULES_PATH = ROOT_DIR / "docs" / "system_rules.md"
DEVELOPER_POLICY_PATH = ROOT_DIR / "docs" / "developer_policy.md"
logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    session_id: uuid.UUID
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
        self, message: str, session_id: uuid.UUID | None, claim_id: uuid.UUID | None
    ) -> ChatResult:
        session = self._get_or_create_session(session_id, claim_id)
        self._store_message(session.id, role="user", content=message)

        messages = self._build_prompt(session.id, claim_id)
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
                tenant_id=self.user.tenant_id,
                user_id=self.user.id,
                chat_session_id=session.id,
            )
            messages.append(self._assistant_tool_call_message(result))
            for tool_call in result.tool_calls:
                if tool_call.name not in allowed_tools:
                    logger.warning("Skipping unknown tool call: %s", tool_call.name)
                    continue
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
                if tool_call.name == "request_form" and isinstance(tool_result, dict):
                    ui_actions.append(tool_result)
                if isinstance(tool_result, dict) and tool_result.get("action_required"):
                    return ChatResult(
                        session_id=session.id,
                        assistant_message="Confirmation required to proceed.",
                        ui_actions=ui_actions,
                        debug=debug if settings.env in {"dev", "test"} else None,
                        action_required=True,
                        proposed_changes=tool_result.get("proposed_changes"),
                    )
                messages.append(self._tool_result_message(tool_call, tool_result))

        return ChatResult(
            session_id=session.id,
            assistant_message="Unable to complete request.",
            ui_actions=ui_actions,
            debug=debug if settings.env in {"dev", "test"} else None,
        )

    def _get_or_create_session(
        self, session_id: uuid.UUID | None, claim_id: uuid.UUID | None
    ) -> ChatSession:
        if session_id:
            session = self.db.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.tenant_id == self.user.tenant_id,
                    ChatSession.user_id == self.user.id,
                )
            ).scalar_one_or_none()
            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
                )
            return session

        if claim_id:
            claim = self.db.execute(
                select(Claim).where(
                    Claim.id == claim_id,
                    Claim.tenant_id == self.user.tenant_id,
                )
            ).scalar_one_or_none()
            if claim is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

        session = ChatSession(
            tenant_id=self.user.tenant_id,
            user_id=self.user.id,
            claim_id=claim_id,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def _build_prompt(
        self, session_id: uuid.UUID, claim_id: uuid.UUID | None
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        messages.append({"role": "system", "content": SYSTEM_RULES_PATH.read_text()})
        messages.append({"role": "system", "content": DEVELOPER_POLICY_PATH.read_text()})

        if claim_id:
            claim = self.db.execute(
                select(Claim).where(
                    Claim.id == claim_id,
                    Claim.tenant_id == self.user.tenant_id,
                )
            ).scalar_one_or_none()
            if claim is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
            patient = self.db.execute(
                select(Patient).where(
                    Patient.id == claim.patient_id,
                    Patient.tenant_id == self.user.tenant_id,
                )
            ).scalar_one_or_none()
            context = {
                "claim": {
                    "id": str(claim.id),
                    "status": claim.status,
                    "amount_cents": claim.amount_cents,
                    "description": claim.description,
                },
                "patient": None,
            }
            if patient:
                context["patient"] = {
                    "id": str(patient.id),
                    "full_name": patient.full_name,
                    "dob": patient.dob.isoformat() if patient.dob else None,
                }
            messages.append({"role": "system", "content": f"Context: {json.dumps(context)}"})

        history = self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(10)
        ).scalars()
        for item in history:
            if item.role in {"user", "assistant"} and item.content:
                messages.append({"role": item.role, "content": item.content})
            elif item.role == "tool" and item.tool_result is not None:
                messages.append(
                    {
                        "role": "tool",
                        "name": item.tool_name or "",
                        "content": json.dumps(item.tool_result),
                    }
                )

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
        self, session_id: uuid.UUID, role: str, content: str | None = None
    ) -> ChatMessage | None:
        if role == "assistant" and (content is None or not content.strip()):
            return None
        message = ChatMessage(
            tenant_id=self.user.tenant_id,
            session_id=session_id,
            role=role,
            content=content,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def _store_tool_call(self, session_id: uuid.UUID, call: ToolCall) -> None:
        if not call.name:
            return
        message = ChatMessage(
            tenant_id=self.user.tenant_id,
            session_id=session_id,
            role="assistant",
            content=None,
            tool_name=call.name,
            tool_args=call.arguments,
        )
        self.db.add(message)
        self.db.commit()

    def _store_tool_result(
        self, session_id: uuid.UUID, tool_name: str, result: dict[str, Any]
    ) -> None:
        if not tool_name or result is None:
            return
        message = ChatMessage(
            tenant_id=self.user.tenant_id,
            session_id=session_id,
            role="tool",
            content=None,
            tool_name=tool_name,
            tool_result=result,
        )
        self.db.add(message)
        self.db.commit()
