"""Chat orchestrator for LLM + tool loop."""

from __future__ import annotations

import json
import logging
import time
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
from app.core.response_cache import invalidate_chat_session_messages_cache
from app.db.id_utils import next_id
from app.db.models import ChatMessage, ChatSession, User
from app.llm.client import ChatCompletionResult, LLMClient, ToolCall
from app.llm.tools import ToolContext, execute_tool, list_tool_schemas
from app.schemas.virtual_claims import VirtualClaimResponse
from app.services.claims.chat_extraction import (
    extract_virtual_claim_patch,
    looks_like_claim_prep_message,
)
from app.services.claims.virtual_claims import (
    get_virtual_claim_state,
    hydrate_virtual_claim_from_tool_result,
    update_virtual_claim_state,
)
from app.utils.time import utcnow

ROOT_DIR = Path(__file__).resolve().parents[2]
SYSTEM_RULES_PATH = ROOT_DIR / "docs" / "system_rules.md"
DEVELOPER_POLICY_PATH = ROOT_DIR / "docs" / "developer_policy.md"
DEFAULT_SYSTEM_RULES = "You are a helpful assistant."
DEFAULT_DEVELOPER_POLICY = "Follow developer instructions."
logger = logging.getLogger(__name__)
CLAIM_PREP_WRITE_KEYWORDS = (
    "create claim",
    "draft claim",
    "materialize",
    "submit claim",
    "create_claim_draft",
    "propose_materialize_virtual_claim",
    "confirm",
)
FIELD_LABELS = {
    "service_date": "Service date",
    "diagnosis.code": "Diagnosis code",
    "diagnosis.description": "Diagnosis description",
    "clinical.radiculopathy": "Radiculopathy symptoms",
    "clinical.dermatomal_distribution": "Dermatomal distribution",
    "clinical.functional_limitation": "Functional limitation",
    "clinical.conservative_treatment": "Conservative treatment failed",
    "clinical.imaging_guidance": "Imaging guidance",
    "clinical.radiology_consistency": "Radiologic findings consistent with symptoms",
    "clinical.neuro_exam": "Neuro exam evidence",
    "clinical.mri_or_emg": "MRI / CT / EMG evidence",
    "treatment.initial_tfesi": "Initial therapeutic TFESI",
    "service.quantity": "Quantity",
    "utilization.level_limit_ok": "Vertebral level limits respected",
    "utilization.frequency_limit_ok": "Frequency / session limits respected",
}


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
    virtual_claim: VirtualClaimResponse | None = None


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

        virtual_claim = self._load_virtual_claim(session.id)
        virtual_claim, updated_keys = self._apply_message_virtual_claim_hints(
            session,
            message,
            virtual_claim,
        )
        fast_path_result = self._maybe_handle_virtual_claim_fast_path(
            session,
            message,
            virtual_claim,
            updated_keys,
        )
        if fast_path_result is not None:
            self._store_message(
                session.id,
                role="assistant",
                content=fast_path_result.assistant_message,
            )
            return fast_path_result
        messages = self._build_prompt(session.id, virtual_claim)
        tools = list_tool_schemas()
        allowed_tools = {tool["function"]["name"] for tool in tools}
        ui_actions: list[dict[str, Any]] = []
        debug: dict[str, Any] = {"tool_steps": 0}

        for step in range(settings.llm_max_steps):
            llm_started = time.monotonic()
            result = self.llm_client.chat_complete(messages=messages, tools=tools)
            logger.info(
                "chat_llm_round session_id=%s step=%s duration_ms=%s tool_calls=%s",
                session.id,
                step + 1,
                round((time.monotonic() - llm_started) * 1000, 2),
                len(result.tool_calls),
            )
            self._store_message(session.id, role="assistant", content=result.assistant_text)

            if not result.tool_calls:
                assistant_message = result.assistant_text.strip()
                if not assistant_message:
                    logger.warning(
                        "llm returned empty assistant message session_id=%s step=%s",
                        session.id,
                        step + 1,
                    )
                    assistant_message = "I couldn't produce a useful response. Please try again."
                return ChatResult(
                    session_id=session.id,
                    assistant_message=assistant_message,
                    ui_actions=self._append_virtual_claim_action(ui_actions, virtual_claim),
                    debug=debug if settings.env in {"dev", "test"} else None,
                    virtual_claim=virtual_claim,
                )

            debug["tool_steps"] = step + 1
            if step == settings.llm_max_steps - 1:
                return ChatResult(
                    session_id=session.id,
                    assistant_message="Reached max tool steps without resolution.",
                    ui_actions=self._append_virtual_claim_action(ui_actions, virtual_claim),
                    debug=debug if settings.env in {"dev", "test"} else None,
                    virtual_claim=virtual_claim,
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
                    tool_started = time.monotonic()
                    tool_result = execute_tool(tool_call.name, tool_call.arguments, tool_context)
                except ValidationError as exc:
                    tool_result = {
                        "error": {
                            "code": "TOOL_VALIDATION_ERROR",
                            "message": "Tool arguments invalid",
                            "details": exc.errors(),
                        }
                    }
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.exception(
                        "tool execution failed session_id=%s tool=%s",
                        session.id,
                        tool_call.name,
                    )
                    tool_result = {
                        "error": {
                            "code": "TOOL_EXECUTION_ERROR",
                            "message": "Tool execution failed",
                            "details": {
                                "tool": tool_call.name,
                                "error": str(exc),
                            },
                        }
                    }
                finally:
                    logger.info(
                        "chat_tool_round session_id=%s step=%s tool=%s duration_ms=%s",
                        session.id,
                        step + 1,
                        tool_call.name,
                        round((time.monotonic() - tool_started) * 1000, 2),
                    )
                self._store_tool_result(session.id, tool_call.name, tool_result)
                virtual_claim = self._hydrate_virtual_claim(session.id, tool_call.name, tool_result)
                virtual_claim, _ignored_updated_keys = self._apply_message_virtual_claim_hints(
                    session,
                    message,
                    virtual_claim,
                )
                log_chat_event(
                    "tool_result",
                    {
                        "user_id": str(self.user.id),
                        "chat_session_id": str(session.id),
                        "tool_name": tool_call.name,
                        "tool_result": self._summarize_payload(tool_result),
                    },
                )
                if (
                    tool_call.name == "request_form"
                    and isinstance(tool_result, dict)
                    and tool_result.get("type") == "form"
                ):
                    ui_actions.append(tool_result)
                if isinstance(tool_result, dict) and tool_result.get("action_required"):
                    proposed_changes = tool_result.get("proposed_changes")
                    proposal_payload = {
                        "proposal_id": str(uuid.uuid4()),
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "proposed_changes": proposed_changes,
                    }
                    if isinstance(proposed_changes, dict) and "patch" in proposed_changes:
                        proposal_payload["patch"] = proposed_changes.get("patch")
                    return ChatResult(
                        session_id=session.id,
                        assistant_message="Confirmation required to proceed.",
                        ui_actions=self._append_virtual_claim_action(ui_actions, virtual_claim),
                        debug=debug if settings.env in {"dev", "test"} else None,
                        action_required=True,
                        proposed_changes=proposal_payload,
                        virtual_claim=virtual_claim,
                    )
                messages.append(self._tool_result_message(tool_call, tool_result))

        return ChatResult(
            session_id=session.id,
            assistant_message="Unable to complete request.",
            ui_actions=self._append_virtual_claim_action(ui_actions, virtual_claim),
            debug=debug if settings.env in {"dev", "test"} else None,
            virtual_claim=virtual_claim,
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

    def _build_prompt(
        self,
        session_id: int,
        virtual_claim: VirtualClaimResponse | None,
    ) -> list[dict[str, Any]]:
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
        if virtual_claim is not None:
            messages.append(
                {
                    "role": "system",
                    "content": self._virtual_claim_system_message(virtual_claim),
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
        content = result.assistant_text.strip() if isinstance(result.assistant_text, str) else ""
        return {
            "role": "assistant",
            "content": content or None,
            "tool_calls": tool_calls,
        }

    def _tool_result_message(self, call: ToolCall, tool_result: dict[str, Any]) -> dict[str, Any]:
        return {
            "role": "tool",
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
        self._invalidate_messages_cache(session_id)
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
        self._invalidate_messages_cache(session_id)

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
        self._invalidate_messages_cache(session_id)

    def _summarize_payload(self, payload: dict[str, Any]) -> str:
        try:
            rendered = json.dumps(payload, default=str)
        except TypeError:
            rendered = str(payload)
        if len(rendered) <= settings.max_context_chars:
            return rendered
        return f"{rendered[: settings.max_context_chars]}…"

    def _invalidate_messages_cache(self, session_id: int) -> None:
        invalidate_chat_session_messages_cache(
            user_id=self.user.id,
            clinic_id=self.user.clinic_id,
            role=self.user.role,
            session_id=session_id,
        )

    def _load_virtual_claim(self, session_id: int) -> VirtualClaimResponse | None:
        return get_virtual_claim_state(
            self.db,
            session_id=session_id,
            doctor_id=self.user.id,
            clinic_id=self.user.clinic_id,
            create_if_missing=False,
        )

    def _hydrate_virtual_claim(
        self,
        session_id: int,
        tool_name: str,
        tool_result: dict[str, Any],
    ) -> VirtualClaimResponse | None:
        return hydrate_virtual_claim_from_tool_result(
            self.db,
            session_id=session_id,
            doctor_id=self.user.id,
            clinic_id=self.user.clinic_id,
            tool_name=tool_name,
            tool_result=tool_result,
        )

    def _append_virtual_claim_action(
        self,
        ui_actions: list[dict[str, Any]],
        virtual_claim: VirtualClaimResponse | None,
    ) -> list[dict[str, Any]]:
        if virtual_claim is None:
            return ui_actions
        actions = [
            action for action in ui_actions if action.get("type") != "virtual_claim_update"
        ]
        actions.append(
            {
                "type": "virtual_claim_update",
                "virtual_claim": virtual_claim.model_dump(mode="json"),
            }
        )
        return actions

    def _apply_message_virtual_claim_hints(
        self,
        session: ChatSession,
        message: str,
        virtual_claim: VirtualClaimResponse | None,
    ) -> tuple[VirtualClaimResponse | None, list[str]]:
        extracted = extract_virtual_claim_patch(message)
        if not extracted.has_updates:
            return virtual_claim, []
        response = update_virtual_claim_state(
            self.db,
            session_id=session.id,
            doctor_id=session.doctor_id,
            clinic_id=session.clinic_id,
            patch={
                "patient_query": extracted.patient_query,
                "insurance_company_name": extracted.insurance_company_name,
                "procedure_code": extracted.procedure_code,
                "fields": [
                    {"key": key, "value": value}
                    for key, value in extracted.fields
                ],
            },
            source_type="llm_extracted",
        )
        updated_keys = list(dict.fromkeys(key for key, _value in extracted.fields))
        if extracted.patient_query:
            updated_keys.insert(0, "patient_id")
        if extracted.insurance_company_name:
            updated_keys.append("insurance_company_id")
        if extracted.procedure_code:
            updated_keys.append("procedure_code")
        return response, updated_keys

    def _maybe_handle_virtual_claim_fast_path(
        self,
        session: ChatSession,
        message: str,
        virtual_claim: VirtualClaimResponse | None,
        updated_keys: list[str],
    ) -> ChatResult | None:
        if virtual_claim is None:
            return None
        lowered = message.lower()
        if "use tools only" in lowered:
            return None
        if any(keyword in lowered for keyword in CLAIM_PREP_WRITE_KEYWORDS):
            return None
        if not updated_keys and not looks_like_claim_prep_message(message):
            return None
        assistant_message = self._build_virtual_claim_summary(
            virtual_claim,
            updated_keys=updated_keys,
        )
        return ChatResult(
            session_id=session.id,
            assistant_message=assistant_message,
            ui_actions=self._append_virtual_claim_action([], virtual_claim),
            debug={"tool_steps": 0} if settings.env in {"dev", "test"} else None,
            virtual_claim=virtual_claim,
        )

    def _virtual_claim_system_message(self, virtual_claim: VirtualClaimResponse) -> str:
        readiness = virtual_claim.checklist.readiness
        patient_name = virtual_claim.patient.name if virtual_claim.patient else "MISSING"
        payer_name = virtual_claim.payer.name if virtual_claim.payer else "MISSING"
        procedure_code = virtual_claim.procedure.code if virtual_claim.procedure else "MISSING"
        service_date = virtual_claim.checklist.service.service_date.value or "MISSING"
        diagnosis_code = virtual_claim.checklist.diagnosis.diagnosis_code.value or "MISSING"
        missing_fields = readiness.missing_fields or []
        next_questions = readiness.next_questions or []
        return (
            "Current session virtual claim checklist is the source of truth for claim-prep state.\n"
            "Before asking for any missing claim field, inspect the existing virtual claim state.\n"
            "Do not ask again for patient, payer, or procedure code when they are already filled.\n"
            "When the user provides clinical facts, update the existing virtual claim instead of "
            "requesting duplicate base identifiers.\n"
            "Use request_form only for fields that remain missing after checking the "
            "virtual claim.\n"
            f"Current patient: {patient_name}\n"
            f"Current payer: {payer_name}\n"
            f"Current procedure code: {procedure_code}\n"
            f"Current service date: {service_date}\n"
            f"Current diagnosis code: {diagnosis_code}\n"
            f"Ready to draft: {readiness.ready_to_draft}\n"
            f"Missing fields: {', '.join(missing_fields) if missing_fields else 'none'}\n"
            "Suggested next questions: "
            f"{' | '.join(next_questions[:3]) if next_questions else 'none'}"
        )

    def _build_virtual_claim_summary(
        self,
        virtual_claim: VirtualClaimResponse,
        *,
        updated_keys: list[str],
    ) -> str:
        updated_lines = self._updated_lines(virtual_claim, updated_keys)
        remaining_missing = virtual_claim.missing_fields[:3]
        next_questions = virtual_claim.follow_up_questions[:3]

        lines = ["UPDATED"]
        lines.extend(updated_lines or ["- No new checklist facts were added from this message."])
        lines.append("")
        lines.append("STILL MISSING")
        if remaining_missing:
            lines.extend(f"- {item.label}" for item in remaining_missing)
        else:
            lines.append("- Nothing required is currently missing.")
        lines.append("")
        lines.append(
            f"READY TO DRAFT: {'YES' if virtual_claim.checklist.readiness.ready_to_draft else 'NO'}"
        )
        if next_questions:
            lines.append("")
            lines.append("NEXT QUESTIONS")
            lines.extend(f"- {item.prompt}" for item in next_questions[:3])
        return "\n".join(lines)

    def _updated_lines(
        self,
        virtual_claim: VirtualClaimResponse,
        updated_keys: list[str],
    ) -> list[str]:
        if not updated_keys:
            return []
        lines: list[str] = []
        unique_keys = list(dict.fromkeys(updated_keys))
        for key in unique_keys:
            if key == "patient_id" and virtual_claim.patient and virtual_claim.patient.name:
                lines.append(f"- Patient: {virtual_claim.patient.name}")
                continue
            if key == "insurance_company_id" and virtual_claim.payer and virtual_claim.payer.name:
                lines.append(f"- Payer: {virtual_claim.payer.name}")
                continue
            if key == "procedure_code" and virtual_claim.procedure and virtual_claim.procedure.code:
                lines.append(f"- CPT: {virtual_claim.procedure.code}")
                continue
            value = self._virtual_claim_value_for_key(virtual_claim, key)
            if value is None:
                continue
            label = FIELD_LABELS.get(key, key)
            lines.append(f"- {label}: {value}")
        return lines

    def _virtual_claim_value_for_key(
        self,
        virtual_claim: VirtualClaimResponse,
        key: str,
    ) -> Any:
        policy = virtual_claim.checklist.policy_medical_necessity
        field_map = {
            "service_date": virtual_claim.checklist.service.service_date.value,
            "diagnosis.code": virtual_claim.checklist.diagnosis.diagnosis_code.value,
            "diagnosis.description": (
                virtual_claim.checklist.diagnosis.diagnosis_description.value
            ),
            "clinical.radiculopathy": policy.radiculopathy_evidence.value,
            "clinical.dermatomal_distribution": policy.dermatomal_distribution.value,
            "clinical.functional_limitation": policy.functional_limitation.value,
            "clinical.conservative_treatment": policy.conservative_treatment_failed.value,
            "clinical.imaging_guidance": policy.imaging_guidance.value,
            "clinical.radiology_consistency": (
                policy.radiologic_findings_consistent.value
                if policy.radiologic_findings_consistent
                else None
            ),
            "clinical.neuro_exam": policy.neuro_exam_evidence.value,
            "clinical.mri_or_emg": policy.MRI_or_CT_or_EMG_evidence.value,
            "treatment.initial_tfesi": (
                policy.initial_therapeutic_tfesi.value
                if policy.initial_therapeutic_tfesi
                else None
            ),
            "service.quantity": virtual_claim.checklist.service.quantity.value,
            "utilization.level_limit_ok": (
                policy.vertebral_level_limits_respected.value
                if policy.vertebral_level_limits_respected
                else None
            ),
            "utilization.frequency_limit_ok": (
                policy.frequency_session_limits_respected.value
            ),
        }
        return field_map.get(key)
