"""Tool registry and execution."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Claim, ClaimEvent, Patient
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
    rows = ctx.db.execute(
        select(Patient).where(
            Patient.tenant_id == ctx.tenant_id,
            Patient.full_name.ilike(query),
        )
    ).scalars()
    patients = [
        {"id": str(patient.id), "full_name": patient.full_name, "dob": patient.dob}
        for patient in rows
    ]
    return {"patients": patients}


def _get_patient(ctx: ToolContext, args: schemas.GetPatientArgs) -> dict[str, Any]:
    patient = ctx.db.execute(
        select(Patient).where(
            Patient.tenant_id == ctx.tenant_id,
            Patient.id == args.patient_id,
        )
    ).scalar_one_or_none()
    if patient is None:
        return {"patient": None}
    return {
        "patient": {
            "id": str(patient.id),
            "full_name": patient.full_name,
            "dob": patient.dob,
            "notes": patient.notes,
        }
    }


def _get_claim(ctx: ToolContext, args: schemas.GetClaimArgs) -> dict[str, Any]:
    claim = ctx.db.execute(
        select(Claim).where(
            Claim.tenant_id == ctx.tenant_id,
            Claim.id == args.claim_id,
        )
    ).scalar_one_or_none()
    if claim is None:
        return {"claim": None}
    return {
        "claim": {
            "id": str(claim.id),
            "patient_id": str(claim.patient_id),
            "status": claim.status,
            "amount_cents": claim.amount_cents,
            "description": claim.description,
        }
    }


def _list_claims(ctx: ToolContext, args: schemas.ListClaimsArgs) -> dict[str, Any]:
    rows = ctx.db.execute(
        select(Claim).where(
            Claim.tenant_id == ctx.tenant_id,
            Claim.patient_id == args.patient_id,
        )
    ).scalars()
    claims = [
        {
            "id": str(claim.id),
            "status": claim.status,
            "amount_cents": claim.amount_cents,
        }
        for claim in rows
    ]
    return {"claims": claims}


def _request_form(_: ToolContext, args: schemas.RequestFormArgs) -> dict[str, Any]:
    return {"type": "form", "fields": args.fields}


def _create_claim_draft(ctx: ToolContext, args: schemas.CreateClaimDraftArgs) -> dict[str, Any]:
    patient = ctx.db.execute(
        select(Patient).where(
            Patient.tenant_id == ctx.tenant_id,
            Patient.id == args.patient_id,
        )
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    proposed = {"patient_id": str(args.patient_id), "fields": args.fields}
    if not args.confirm:
        return {"action_required": True, "proposed_changes": proposed}

    claim = Claim(
        tenant_id=ctx.tenant_id,
        patient_id=patient.id,
        status="draft",
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
    claim = ctx.db.execute(
        select(Claim).where(
            Claim.tenant_id == ctx.tenant_id,
            Claim.id == args.claim_id,
        )
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    allowed_fields = {"status", "amount_cents", "description"}
    patch = {key: value for key, value in args.patch.items() if key in allowed_fields}
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
