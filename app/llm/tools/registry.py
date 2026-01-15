"""Tool registry and execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import Claim, ClaimStatus, InsuranceCompany, Patient, User
from app.llm.tools import schemas
from app.utils.time import utcnow

Handler = Callable[["ToolContext", Any], dict[str, Any]]


@dataclass(frozen=True)
class ToolContext:
    db: Session
    user_id: int | None = None
    chat_session_id: int | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Handler


def _search_patients(ctx: ToolContext, args: schemas.SearchPatientsArgs) -> dict[str, Any]:
    query = f"%{args.query}%"
    filters = []
    if ctx.user_id is not None:
        filters.append(Patient.doctor_id == ctx.user_id)
    rows = ctx.db.execute(
        select(Patient).where(
            *filters,
            or_(
                Patient.first_name.ilike(query),
                Patient.last_name.ilike(query),
            ),
        )
    ).scalars()
    patients = [
        {
            "id": patient.id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        }
        for patient in rows
    ]
    return {"patients": patients}


def _get_patient(ctx: ToolContext, args: schemas.GetPatientArgs) -> dict[str, Any]:
    filters = [Patient.id == args.patient_id]
    if ctx.user_id is not None:
        filters.append(Patient.doctor_id == ctx.user_id)
    patient = ctx.db.execute(select(Patient).where(*filters)).scalar_one_or_none()
    if patient is None:
        return {"patient": None}
    return {
        "patient": {
            "id": patient.id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        }
    }


def _get_claim(ctx: ToolContext, args: schemas.GetClaimArgs) -> dict[str, Any]:
    claim = ctx.db.execute(
        select(Claim, Patient)
        .join(Patient)
        .where(
            Claim.id == args.claim_id,
            *([Patient.doctor_id == ctx.user_id] if ctx.user_id is not None else []),
        )
    ).first()
    if claim is None:
        return {"claim": None}
    claim_row, patient = claim
    return {
        "claim": {
            "id": claim_row.id,
            "patient_id": claim_row.patient_id,
            "claim_status": claim_row.claim_status,
            "claim_number": claim_row.claim_number,
            "insurance_company_id": claim_row.insurance_company_id,
            "service_date": claim_row.service_date.isoformat() if claim_row.service_date else None,
            "claim_date": claim_row.claim_date.isoformat() if claim_row.claim_date else None,
            "billed_amount_total": float(claim_row.billed_amount_total)
            if claim_row.billed_amount_total is not None
            else None,
        }
    }


def _list_claims(ctx: ToolContext, args: schemas.ListClaimsArgs) -> dict[str, Any]:
    rows = ctx.db.execute(
        select(Claim)
        .join(Patient)
        .where(
            Claim.patient_id == args.patient_id,
            *([Patient.doctor_id == ctx.user_id] if ctx.user_id is not None else []),
        )
    ).scalars()
    claims = [
        {
            "id": claim.id,
            "claim_status": claim.claim_status,
            "billed_amount_total": float(claim.billed_amount_total)
            if claim.billed_amount_total is not None
            else None,
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
        )
    ).scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")
    email = user.email or ""
    return {"email": email, "user_id": user.id, "greeting": f"Hello, {email}!"}


def _time_now(_: ToolContext, args: schemas.TimeNowArgs) -> dict[str, Any]:
    tz = args.tz or "Asia/Tbilisi"
    now = datetime.now(ZoneInfo(tz)).isoformat(timespec="seconds")
    return {"now": now, "tz": tz}


def _create_claim_draft(ctx: ToolContext, args: schemas.CreateClaimDraftArgs) -> dict[str, Any]:
    filters = [Patient.id == args.patient_id]
    if ctx.user_id is not None:
        filters.append(Patient.doctor_id == ctx.user_id)
    patient = ctx.db.execute(select(Patient).where(*filters)).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    proposed = {"patient_id": str(args.patient_id), "fields": args.fields}
    if not args.confirm:
        return {"action_required": True, "proposed_changes": proposed}

    insurance_company_id = args.fields.get("insurance_company_id")
    if insurance_company_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="insurance_company_id is required",
        )
    company = ctx.db.get(InsuranceCompany, insurance_company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance company not found",
        )
    claim = Claim(
        id=next_id(ctx.db, Claim),
        doctor_id=patient.doctor_id,
        patient_id=patient.id,
        insurance_company_id=insurance_company_id,
        claim_status=ClaimStatus.DRAFT.value,
        claim_number=args.fields.get("claim_number"),
        service_date=args.fields.get("service_date"),
        claim_date=args.fields.get("claim_date"),
        billed_amount_total=args.fields.get("billed_amount_total"),
        allowed_amount_total=args.fields.get("allowed_amount_total"),
        coinsurance_amount_total=args.fields.get("coinsurance_amount_total"),
        copay_amount_total=args.fields.get("copay_amount_total"),
        deductible_amount_total=args.fields.get("deductible_amount_total"),
        created_at=utcnow(),
    )
    ctx.db.add(claim)
    ctx.db.commit()
    return {"claim_id": claim.id}


def _update_claim_fields(ctx: ToolContext, args: schemas.UpdateClaimFieldsArgs) -> dict[str, Any]:
    filters = [Claim.id == args.claim_id]
    if ctx.user_id is not None:
        filters.append(Patient.doctor_id == ctx.user_id)
    claim = ctx.db.execute(
        select(Claim)
        .join(Patient)
        .where(
            *filters,
        )
    ).scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    allowed_fields = {
        "claim_status",
        "claim_number",
        "service_date",
        "claim_date",
        "billed_amount_total",
        "allowed_amount_total",
        "coinsurance_amount_total",
        "copay_amount_total",
        "deductible_amount_total",
    }
    patch = {key: value for key, value in args.patch.items() if key in allowed_fields}
    if "claim_status" in patch and isinstance(patch["claim_status"], str):
        status_value = patch["claim_status"].strip().upper()
        if status_value in ClaimStatus.__members__:
            patch["claim_status"] = ClaimStatus[status_value].value
    proposed = {"claim_id": str(args.claim_id), "patch": patch}
    if not args.confirm:
        return {"action_required": True, "proposed_changes": proposed}

    for key, value in patch.items():
        setattr(claim, key, value)
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
