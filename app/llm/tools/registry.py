"""Tool registry and execution."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Claim, ClaimEvent, ClaimStatus, Patient, User
from app.llm.tools import schemas

Handler = Callable[["ToolContext", Any], dict[str, Any]]


@dataclass(frozen=True)
class ToolContext:
    db: Session
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    chat_session_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Handler


def _search_patients(ctx: ToolContext, args: schemas.SearchPatientsArgs) -> dict[str, Any]:
    query = f"%{args.query}%"
    filters = [Patient.tenant_id == ctx.tenant_id]
    if ctx.user_id is not None:
        filters.append(Patient.user_id == ctx.user_id)
    rows = ctx.db.execute(
        select(Patient).where(
            *filters,
            or_(
                Patient.first_name.ilike(query),
                Patient.last_name.ilike(query),
                Patient.full_name.ilike(query),
            ),
        )
    ).scalars()
    patients = [
        {
            "id": str(patient.id),
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "full_name": patient.full_name,
            "date_of_birth": patient.date_of_birth.isoformat()
            if patient.date_of_birth
            else None,
        }
        for patient in rows
    ]
    return {"patients": patients}


def _get_patient(ctx: ToolContext, args: schemas.GetPatientArgs) -> dict[str, Any]:
    filters = [Patient.tenant_id == ctx.tenant_id, Patient.id == args.patient_id]
    if ctx.user_id is not None:
        filters.append(Patient.user_id == ctx.user_id)
    patient = ctx.db.execute(
        select(Patient).where(*filters)
    ).scalar_one_or_none()
    if patient is None:
        return {"patient": None}
    return {
        "patient": {
            "id": str(patient.id),
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat()
            if patient.date_of_birth
            else None,
            "sex": patient.sex,
            "notes": patient.notes,
        }
    }


def _get_claim(ctx: ToolContext, args: schemas.GetClaimArgs) -> dict[str, Any]:
    claim = ctx.db.execute(
        select(Claim, Patient).join(Patient).where(
            Claim.tenant_id == ctx.tenant_id,
            Claim.id == args.claim_id,
            Patient.tenant_id == ctx.tenant_id,
            *( [Patient.user_id == ctx.user_id] if ctx.user_id is not None else [] ),
        )
    ).first()
    if claim is None:
        return {"claim": None}
    claim_row, patient = claim
    return {
        "claim": {
            "id": str(claim_row.id),
            "patient_id": str(claim_row.patient_id),
            "status": claim_row.status.value
            if hasattr(claim_row.status, "value")
            else claim_row.status,
            "claim_number": claim_row.claim_number,
            "agency_id": str(claim_row.agency_id) if claim_row.agency_id else None,
            "service_from": claim_row.service_from.isoformat()
            if claim_row.service_from
            else None,
            "service_to": claim_row.service_to.isoformat() if claim_row.service_to else None,
            "amount_cents": claim_row.amount_cents,
            "description": claim_row.description,
        }
    }


def _list_claims(ctx: ToolContext, args: schemas.ListClaimsArgs) -> dict[str, Any]:
    rows = ctx.db.execute(
        select(Claim)
        .join(Patient)
        .where(
            Claim.tenant_id == ctx.tenant_id,
            Claim.patient_id == args.patient_id,
            Patient.tenant_id == ctx.tenant_id,
            *( [Patient.user_id == ctx.user_id] if ctx.user_id is not None else [] ),
        )
    ).scalars()
    claims = [
        {
            "id": str(claim.id),
            "status": claim.status.value if hasattr(claim.status, "value") else claim.status,
            "amount_cents": claim.amount_cents,
        }
        for claim in rows
    ]
    return {"claims": claims}


def _request_form(_: ToolContext, args: schemas.RequestFormArgs) -> dict[str, Any]:
    return {"type": "form", "fields": args.fields}


def _get_account(ctx: ToolContext, _: schemas.GetAccountArgs) -> dict[str, Any]:
    if ctx.user_id is None:
        raise ValueError("User not found")
    user = ctx.db.execute(
        select(User).where(
            User.id == ctx.user_id,
            User.tenant_id == ctx.tenant_id,
        )
    ).scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")
    email = user.email or ""
    return {"email": email, "user_id": str(user.id), "greeting": f"Hello, {email}!"}


def _time_now(_: ToolContext, args: schemas.TimeNowArgs) -> dict[str, Any]:
    tz = args.tz or "Asia/Tbilisi"
    now = datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")
    return {"now": now, "tz": tz}


def _create_claim_draft(ctx: ToolContext, args: schemas.CreateClaimDraftArgs) -> dict[str, Any]:
    filters = [Patient.tenant_id == ctx.tenant_id, Patient.id == args.patient_id]
    if ctx.user_id is not None:
        filters.append(Patient.user_id == ctx.user_id)
    patient = ctx.db.execute(
        select(Patient).where(*filters)
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    proposed = {"patient_id": str(args.patient_id), "fields": args.fields}
    if not args.confirm:
        return {"action_required": True, "proposed_changes": proposed}

    agency_id = args.fields.get("agency_id")
    agency_uuid = None
    if agency_id:
        try:
            agency_uuid = uuid.UUID(str(agency_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid agency_id",
            ) from None

    claim = Claim(
        tenant_id=ctx.tenant_id,
        patient_id=patient.id,
        agency_id=agency_uuid,
        status=ClaimStatus.DRAFT,
        claim_number=args.fields.get("claim_number"),
        service_from=args.fields.get("service_from"),
        service_to=args.fields.get("service_to"),
        amount_cents=args.fields.get("amount_cents"),
        description=args.fields.get("description"),
        extra=args.fields,
    )
    ctx.db.add(claim)
    ctx.db.flush()
    ctx.db.add(
        ClaimEvent(
            tenant_id=ctx.tenant_id,
            claim_id=claim.id,
            user_id=ctx.user_id,
            chat_session_id=ctx.chat_session_id,
            event_type="create_claim_draft",
            payload=proposed,
        )
    )
    ctx.db.commit()
    return {"claim_id": str(claim.id)}


def _update_claim_fields(ctx: ToolContext, args: schemas.UpdateClaimFieldsArgs) -> dict[str, Any]:
    filters = [Claim.tenant_id == ctx.tenant_id, Claim.id == args.claim_id]
    if ctx.user_id is not None:
        filters.append(Patient.user_id == ctx.user_id)
    claim = ctx.db.execute(
        select(Claim)
        .join(Patient)
        .where(
            *filters,
            Patient.tenant_id == ctx.tenant_id,
        )
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    allowed_fields = {
        "status",
        "amount_cents",
        "description",
        "claim_number",
        "service_from",
        "service_to",
    }
    patch = {key: value for key, value in args.patch.items() if key in allowed_fields}
    if "status" in patch and isinstance(patch["status"], str):
        status_value = patch["status"].strip().upper()
        if status_value in ClaimStatus.__members__:
            patch["status"] = ClaimStatus[status_value]
    proposed = {"claim_id": str(args.claim_id), "patch": patch}
    if not args.confirm:
        return {"action_required": True, "proposed_changes": proposed}

    for key, value in patch.items():
        setattr(claim, key, value)
    ctx.db.add(
        ClaimEvent(
            tenant_id=ctx.tenant_id,
            claim_id=claim.id,
            user_id=ctx.user_id,
            chat_session_id=ctx.chat_session_id,
            event_type="update_claim_fields",
            payload=proposed,
        )
    )
    ctx.db.commit()
    return {"updated": True}


TOOLS: dict[str, ToolDefinition] = {
    "search_patients": ToolDefinition(
        name="search_patients",
        description="Search patients by name.",
        args_model=schemas.SearchPatientsArgs,
        handler=_search_patients,
    ),
    "get_patient": ToolDefinition(
        name="get_patient",
        description="Get a patient by id.",
        args_model=schemas.GetPatientArgs,
        handler=_get_patient,
    ),
    "get_claim": ToolDefinition(
        name="get_claim",
        description="Get a claim by id.",
        args_model=schemas.GetClaimArgs,
        handler=_get_claim,
    ),
    "list_claims": ToolDefinition(
        name="list_claims",
        description="List claims for a patient.",
        args_model=schemas.ListClaimsArgs,
        handler=_list_claims,
    ),
    "request_form": ToolDefinition(
        name="request_form",
        description="Request structured form fields from the user.",
        args_model=schemas.RequestFormArgs,
        handler=_request_form,
    ),
    "get_account": ToolDefinition(
        name="get_account",
        description="Get the current user's account info.",
        args_model=schemas.GetAccountArgs,
        handler=_get_account,
    ),
    "time_now": ToolDefinition(
        name="time_now",
        description="Get current time in a timezone.",
        args_model=schemas.TimeNowArgs,
        handler=_time_now,
    ),
    "create_claim_draft": ToolDefinition(
        name="create_claim_draft",
        description="Create a claim draft (requires confirmation).",
        args_model=schemas.CreateClaimDraftArgs,
        handler=_create_claim_draft,
    ),
    "update_claim_fields": ToolDefinition(
        name="update_claim_fields",
        description="Update claim fields (requires confirmation).",
        args_model=schemas.UpdateClaimFieldsArgs,
        handler=_update_claim_fields,
    ),
}


def list_tool_schemas() -> list[dict[str, Any]]:
    tools = []
    for definition in TOOLS.values():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": definition.args_model.model_json_schema(),
                },
            }
        )
    return tools


def validate_tool_args(tool_name: str, args: dict[str, Any]) -> BaseModel:
    if tool_name not in TOOLS:
        raise KeyError(tool_name)
    model = TOOLS[tool_name].args_model
    return model.model_validate(args)


def execute_tool(tool_name: str, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    if tool_name not in TOOLS:
        return {"error": {"code": "UNKNOWN_TOOL", "message": "Unknown tool"}}
    definition = TOOLS[tool_name]
    validated = definition.args_model.model_validate(args)
    return definition.handler(ctx, validated)
