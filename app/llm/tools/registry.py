"""Tool registry and execution."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.id_utils import next_id
from app.db.models import (
    Claim,
    ClaimLineCoverage,
    ClaimStatus,
    InsuranceCompany,
    McpCode,
    Patient,
    PolicyLink,
    PolicyRule,
    User,
)
from app.llm.tools import schemas
from app.services.policy.rules_refresh import parse_policy_link_and_store
from app.utils.time import utcnow

BOT_CAPABILITIES_VERSION = "1.0"
BOT_CAPABILITIES_NAME = "Sphere Coverage Assistant"
BOT_CAPABILITIES_CATEGORIES = ("all", "procedure_codes", "policies", "claims", "system")
BOT_CAPABILITIES_LANGUAGES = ("ru", "en")

TOOL_METADATA: dict[str, dict[str, Any]] = {
    "list_procedure_codes": {
        "categories": ["procedure_codes"],
        "summary": {
            "ru": "Список или поиск доступных кодов процедур (CPT) по коду или описанию.",
            "en": "List or search available procedure (CPT) codes by code or description.",
        },
        "examples": {
            "ru": [
                "Найди коды, начинающиеся на 27",
                "Покажи коды по описанию 'injection'",
            ],
            "en": ["Find codes starting with 27", "Search codes by description 'injection'"],
        },
        "limits": {
            "ru": ["Ограничение выдачи до 200 строк за запрос."],
            "en": ["Result limit up to 200 rows per request."],
        },
    },
    "get_procedure_code": {
        "categories": ["procedure_codes"],
        "summary": {
            "ru": "Получить описание конкретного кода процедуры.",
            "en": "Get details for a specific procedure code.",
        },
        "examples": {"ru": ["Описание кода 27096"], "en": ["Describe code 27096"]},
        "limits": {"ru": [], "en": []},
    },
    "explain_coverage_for_code": {
        "categories": ["procedure_codes", "policies"],
        "summary": {
            "ru": "Сводка покрытий по коду: политики и наблюдённые статусы в системе.",
            "en": "Coverage summary by code using stored policy rules and observed outcomes.",
        },
        "examples": {
            "ru": [
                "Покажи покрытие CPT 27096",
                "Проверить CPT 27096 для claim_id=123",
            ],
            "en": ["Coverage for CPT 27096", "Check CPT 27096 for claim_id=123"],
        },
        "limits": {
            "ru": ["Данные основаны только на правилах/исходах, сохранённых в системе."],
            "en": ["Based only on stored rules and observed outcomes in the system."],
        },
    },
    "list_policy_links_for_code": {
        "categories": ["policies"],
        "summary": {
            "ru": "Список ссылок на политики для заданного кода.",
            "en": "List policy links for a given code.",
        },
        "examples": {
            "ru": ["Ссылки политики для CPT 27096"],
            "en": ["Policy links for CPT 27096"],
        },
        "limits": {"ru": [], "en": []},
    },
    "get_policy_rules_for_link": {
        "categories": ["policies"],
        "summary": {
            "ru": "Последние извлечённые правила для policy_link_id.",
            "en": "Latest extracted rules for a policy_link_id.",
        },
        "examples": {
            "ru": ["Правила по policy_link_id 555"],
            "en": ["Rules for policy_link_id 555"],
        },
        "limits": {"ru": [], "en": []},
    },
    "get_claim": {
        "categories": ["claims"],
        "summary": {"ru": "Получить данные по claim_id.", "en": "Get claim details by id."},
        "examples": {"ru": ["Покажи claim_id 123"], "en": ["Show claim_id 123"]},
        "limits": {
            "ru": ["Доступ только к вашим заявкам."],
            "en": ["Access limited to your claims."],
        },
    },
    "list_claims": {
        "categories": ["claims"],
        "summary": {"ru": "Список заявок пациента.", "en": "List claims for a patient."},
        "examples": {
            "ru": ["Список claims для patient_id 77"],
            "en": ["List claims for patient_id 77"],
        },
        "limits": {"ru": [], "en": []},
    },
    "get_bot_capabilities": {
        "categories": ["system"],
        "summary": {
            "ru": "Список доступных инструментов и их возможностей.",
            "en": "List available tools and their capabilities.",
        },
        "examples": {"ru": ["Что ты умеешь?"], "en": ["What can you do?"]},
        "limits": {
            "ru": ["Отображает только реально зарегистрированные инструменты."],
            "en": ["Shows only tools registered in the system."],
        },
    },
    "get_account": {
        "categories": ["system"],
        "summary": {"ru": "Информация о текущем пользователе.", "en": "Current user account info."},
        "examples": {"ru": ["Покажи мой аккаунт"], "en": ["Show my account"]},
        "limits": {"ru": [], "en": []},
    },
    "time_now": {
        "categories": ["system"],
        "summary": {"ru": "Текущее время в заданной зоне.", "en": "Current time in a timezone."},
        "examples": {"ru": ["Время в Asia/Tbilisi"], "en": ["Time in Asia/Tbilisi"]},
        "limits": {"ru": [], "en": []},
    },
}

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


def _tool_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def _find_patient_for_context(ctx: ToolContext, patient_id: int) -> Patient | None:
    filters = [Patient.id == patient_id]
    if ctx.user_id is not None:
        filters.append(Patient.doctor_id == ctx.user_id)
    return ctx.db.execute(select(Patient).where(*filters)).scalar_one_or_none()


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
    patient = _find_patient_for_context(ctx, args.patient_id)
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
    patient = _find_patient_for_context(ctx, args.patient_id)
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


def _require_admin(ctx: ToolContext) -> None:
    if ctx.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    user = ctx.db.execute(select(User).where(User.id == ctx.user_id)).scalar_one_or_none()
    if user is None or not any(role.code == "admin" for role in user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")


def _parse_policy_link_and_store(
    ctx: ToolContext, args: schemas.ParsePolicyLinkAndStoreArgs
) -> dict[str, Any]:
    _require_admin(ctx)
    return parse_policy_link_and_store(
        policy_link_id=args.policy_link_id,
        confirm=args.confirm,
        db=ctx.db,
    )


def _list_procedure_codes(ctx: ToolContext, args: schemas.ListProcedureCodesArgs) -> dict[str, Any]:
    query = (args.query or "").strip()
    stmt = select(McpCode)
    if query:
        if query.isdigit():
            stmt = stmt.where(McpCode.code.ilike(f"{query}%"))
        else:
            stmt = stmt.where(McpCode.description.ilike(f"%{query}%"))
    rows = ctx.db.execute(stmt.order_by(McpCode.code.asc()).limit(args.limit)).scalars().all()
    items = [{"code": row.code, "description": row.description} for row in rows]
    return {"items": items, "count": len(items)}


def _get_procedure_code(ctx: ToolContext, args: schemas.GetProcedureCodeArgs) -> dict[str, Any]:
    code = args.code.strip()
    row = ctx.db.execute(select(McpCode).where(McpCode.code == code)).scalar_one_or_none()
    if row is None:
        return {"code": code, "description": None, "exists": False}
    return {"code": row.code, "description": row.description, "exists": True}


def _list_policy_links_for_code(
    ctx: ToolContext, args: schemas.ListPolicyLinksForCodeArgs
) -> dict[str, Any]:
    stmt = select(PolicyLink).where(PolicyLink.mcp_code == args.code)
    if args.insurance_company_id is not None:
        stmt = stmt.where(PolicyLink.insurance_company_id == args.insurance_company_id)
    rows = ctx.db.execute(
        stmt.order_by(PolicyLink.insurance_company_id.asc(), PolicyLink.policy_url.asc())
    ).scalars()
    links = [
        {
            "policy_link_id": row.id,
            "insurance_company_id": row.insurance_company_id,
            "policy_url": row.policy_url,
        }
        for row in rows
    ]
    return {"code": args.code, "links": links}


def _get_policy_rules_for_link(
    ctx: ToolContext, args: schemas.GetPolicyRulesForLinkArgs
) -> dict[str, Any]:
    link = ctx.db.execute(
        select(PolicyLink).where(PolicyLink.id == args.policy_link_id)
    ).scalar_one_or_none()
    if link is None:
        return _tool_error(
            "NOT_FOUND",
            "Policy link not found",
            {"policy_link_id": args.policy_link_id},
        )
    rule = (
        ctx.db.execute(
            select(PolicyRule)
            .where(PolicyRule.policy_link_id == args.policy_link_id)
            .order_by(PolicyRule.extracted_at.desc())
        )
        .scalars()
        .first()
    )
    if rule is None:
        return {"policy_link_id": args.policy_link_id, "found": False}

    rules_payload: Any = rule.rules_json
    if rule.rules_json:
        try:
            parsed = json.loads(rule.rules_json)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict | list):
            rules_payload = parsed

    return {
        "policy_link_id": rule.policy_link_id,
        "title": rule.title,
        "extracted_at": rule.extracted_at.isoformat(),
        "next_review_iso": rule.next_review_iso.isoformat() if rule.next_review_iso else None,
        "rules_json": rules_payload,
        "criteria_json": rule.criteria_json,
        "notes_json": rule.notes_json,
    }


def _explain_coverage_for_code(
    ctx: ToolContext, args: schemas.ExplainCoverageForCodeArgs
) -> dict[str, Any]:
    if ctx.user_id is None:
        return _tool_error("FORBIDDEN", "User not available")

    claim_context = {"claim_id": None, "insurance_company_id": None, "service_date": None}
    claim = None
    if args.claim_id is not None:
        claim = ctx.db.execute(
            select(Claim).where(Claim.id == args.claim_id, Claim.doctor_id == ctx.user_id)
        ).scalar_one_or_none()
        if claim is None:
            return _tool_error("NOT_FOUND", "Claim not found", {"claim_id": args.claim_id})
        claim_context = {
            "claim_id": claim.id,
            "insurance_company_id": claim.insurance_company_id,
            "service_date": claim.service_date.isoformat() if claim.service_date else None,
        }

    links = ctx.db.execute(
        select(PolicyLink)
        .where(PolicyLink.mcp_code == args.code)
        .order_by(PolicyLink.insurance_company_id.asc(), PolicyLink.policy_url.asc())
    ).scalars()
    link_items = [
        {
            "policy_link_id": row.id,
            "insurance_company_id": row.insurance_company_id,
            "policy_url": row.policy_url,
        }
        for row in links
    ]

    link_ids = [item["policy_link_id"] for item in link_items]
    latest_rules: list[dict[str, Any]] = []
    if link_ids:
        rule_rows = ctx.db.execute(
            select(PolicyRule)
            .where(PolicyRule.policy_link_id.in_(link_ids))
            .order_by(PolicyRule.policy_link_id.asc(), PolicyRule.extracted_at.desc())
        ).scalars()
        seen: set[int] = set()
        for rule in rule_rows:
            if rule.policy_link_id in seen:
                continue
            seen.add(rule.policy_link_id)
            latest_rules.append(
                {
                    "policy_link_id": rule.policy_link_id,
                    "title": rule.title,
                    "extracted_at": rule.extracted_at.isoformat(),
                    "next_review_iso": rule.next_review_iso.isoformat()
                    if rule.next_review_iso
                    else None,
                    "criteria_json": rule.criteria_json,
                    "notes_json": rule.notes_json,
                }
            )

    coverage_filters = [
        ClaimLineCoverage.mcp_code == args.code,
        Claim.doctor_id == ctx.user_id,
    ]
    total_rows = ctx.db.execute(
        select(func.count())
        .select_from(ClaimLineCoverage)
        .join(Claim, ClaimLineCoverage.claim_id == Claim.id)
        .where(*coverage_filters)
    ).scalar_one()
    total_rows = int(total_rows or 0)

    status_rows = ctx.db.execute(
        select(ClaimLineCoverage.status, func.count())
        .select_from(ClaimLineCoverage)
        .join(Claim, ClaimLineCoverage.claim_id == Claim.id)
        .where(*coverage_filters)
        .group_by(ClaimLineCoverage.status)
    ).all()
    status_counts = {status: int(count) for status, count in status_rows}

    reason_rows = ctx.db.execute(
        select(ClaimLineCoverage.reason, func.count())
        .select_from(ClaimLineCoverage)
        .join(Claim, ClaimLineCoverage.claim_id == Claim.id)
        .where(
            *coverage_filters,
            ClaimLineCoverage.reason.is_not(None),
            ClaimLineCoverage.reason != "",
        )
        .group_by(ClaimLineCoverage.reason)
        .order_by(func.count().desc())
        .limit(5)
    ).all()
    top_reasons = [{"reason": reason, "count": int(count)} for reason, count in reason_rows]

    example_rows = ctx.db.execute(
        select(ClaimLineCoverage)
        .join(Claim, ClaimLineCoverage.claim_id == Claim.id)
        .where(*coverage_filters)
        .order_by(ClaimLineCoverage.created_at.desc())
        .limit(args.max_examples)
    ).scalars()
    examples = [
        {
            "claim_id": row.claim_id,
            "status": row.status,
            "reason": row.reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in example_rows
    ]

    claim_line = None
    matching_link_count = 0
    if claim is not None:
        claim_line = ctx.db.execute(
            select(ClaimLineCoverage).where(
                ClaimLineCoverage.claim_id == claim.id,
                ClaimLineCoverage.mcp_code == args.code,
            )
        ).scalar_one_or_none()
        matching_link_count = sum(
            1 for item in link_items if item["insurance_company_id"] == claim.insurance_company_id
        )

    hint_parts: list[str] = []
    if claim is not None:
        hint_parts.append(f"Claim {claim.id} insurer {claim.insurance_company_id}.")
        if claim_line is not None:
            reason = f" reason={claim_line.reason}" if claim_line.reason else ""
            hint_parts.append(f"Existing claim coverage row status={claim_line.status}{reason}.")
        else:
            hint_parts.append("No coverage row for this claim/code.")
    if link_items:
        if claim is not None:
            hint_parts.append(
                f"{len(link_items)} policy link(s) for code; "
                f"{matching_link_count} match claim insurer."
            )
        else:
            hint_parts.append(f"{len(link_items)} policy link(s) for code.")
    else:
        hint_parts.append("No policy links stored for this code.")
    if latest_rules:
        hint_parts.append(f"{len(latest_rules)} latest policy rule(s) available.")
    else:
        hint_parts.append("No extracted policy rules stored.")
    if total_rows:
        hint_parts.append(f"Observed {total_rows} coverage outcome row(s) across your claims.")
    else:
        hint_parts.append("No observed coverage outcomes yet.")
    hint_parts.append("Answer based on stored policy links/rules and observed outcomes.")
    answer_hint = " ".join(hint_parts)

    return {
        "code": args.code,
        "claim_context": claim_context,
        "policy": {"links": link_items, "latest_rules": latest_rules},
        "observed_coverage": {
            "summary": {
                "total_rows": total_rows,
                "status_counts": status_counts,
                "top_reasons": top_reasons,
            },
            "examples": examples,
        },
        "answer_hint": answer_hint,
    }


def _normalize_categories(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, Iterable):
        return [item for item in raw if isinstance(item, str)]
    return []


def _infer_tool_categories(definition: ToolDefinition) -> list[str]:
    field_names = set(definition.args_model.model_fields.keys())
    if "claim_id" in field_names or definition.name.startswith("claim_"):
        return ["claims"]
    if "claim" in definition.name or "claim" in definition.description.lower():
        return ["claims"]
    if "patient" in definition.name or "patient" in definition.description.lower():
        return ["claims"]
    if "policy" in definition.name or "policy" in definition.description.lower():
        return ["policies"]
    if "procedure" in definition.name or "mcp" in definition.description.lower():
        return ["procedure_codes"]
    return ["system"]


def _localized(meta: dict[str, Any], key: str, language: str, fallback: Any) -> Any:
    payload = meta.get(key, {})
    if isinstance(payload, dict):
        if language in payload:
            return payload[language]
        return payload.get("en", fallback)
    return payload or fallback


def _get_bot_capabilities(_: ToolContext, args: schemas.GetBotCapabilitiesArgs) -> dict[str, Any]:
    if args.category not in BOT_CAPABILITIES_CATEGORIES:
        return _tool_error(
            "TOOL_VALIDATION_ERROR",
            "Unsupported category",
            {"allowed": list(BOT_CAPABILITIES_CATEGORIES)},
        )
    if args.language not in BOT_CAPABILITIES_LANGUAGES:
        return _tool_error(
            "TOOL_VALIDATION_ERROR",
            "Unsupported language",
            {"allowed": list(BOT_CAPABILITIES_LANGUAGES)},
        )

    categories: dict[str, list[dict[str, Any]]] = {
        "procedure_codes": [],
        "policies": [],
        "claims": [],
        "system": [],
    }
    for definition in TOOLS.values():
        meta = TOOL_METADATA.get(definition.name, {})
        tool_categories = _normalize_categories(meta.get("categories"))
        if not tool_categories:
            tool_categories = _infer_tool_categories(definition)

        for category_id in tool_categories:
            if category_id not in categories:
                continue
            if args.category != "all" and category_id != args.category:
                continue
            summary = _localized(meta, "summary", args.language, definition.description)
            examples = _localized(meta, "examples", args.language, [])
            limits = _localized(meta, "limits", args.language, [])
            capability = {
                "tool": definition.name,
                "summary": summary,
                "examples": examples,
                "limits": limits,
            }
            if args.include_schemas:
                capability["input_schema"] = definition.args_model.model_json_schema()
            categories[category_id].append(capability)

    title_map = {
        "ru": {
            "procedure_codes": "Коды процедур",
            "policies": "Политики и правила",
            "claims": "Заявки и пациенты",
            "system": "Системные возможности",
        },
        "en": {
            "procedure_codes": "Procedure Codes",
            "policies": "Policies & Rules",
            "claims": "Claims & Patients",
            "system": "System Capabilities",
        },
    }
    category_ids = ["procedure_codes", "policies", "claims", "system"]
    if args.category != "all":
        category_ids = [args.category]
    response_categories = []
    for category_id in category_ids:
        response_categories.append(
            {
                "id": category_id,
                "title": title_map[args.language][category_id],
                "capabilities": categories[category_id],
            }
        )

    global_limits = (
        [
            "Список формируется только из зарегистрированных инструментов.",
            "Доступ к данным ограничен вашим аккаунтом.",
            "Некоторые инструменты могут требовать подтверждения при изменениях.",
        ]
        if args.language == "ru"
        else [
            "The list is generated only from registered tools.",
            "Data access is scoped to your account.",
            "Some tools may require confirmation for changes.",
        ]
    )

    return {
        "name": BOT_CAPABILITIES_NAME,
        "version": BOT_CAPABILITIES_VERSION,
        "generated_at": utcnow().isoformat(),
        "categories": response_categories,
        "global_limits": global_limits,
    }


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
    "list_procedure_codes": ToolDefinition(
        name="list_procedure_codes",
        description="List or search procedure codes by code prefix or description.",
        args_model=schemas.ListProcedureCodesArgs,
        handler=_list_procedure_codes,
    ),
    "get_procedure_code": ToolDefinition(
        name="get_procedure_code",
        description="Get details for a procedure code.",
        args_model=schemas.GetProcedureCodeArgs,
        handler=_get_procedure_code,
    ),
    "list_policy_links_for_code": ToolDefinition(
        name="list_policy_links_for_code",
        description="List policy links for a procedure code.",
        args_model=schemas.ListPolicyLinksForCodeArgs,
        handler=_list_policy_links_for_code,
    ),
    "get_policy_rules_for_link": ToolDefinition(
        name="get_policy_rules_for_link",
        description="Get latest policy rules for a policy link.",
        args_model=schemas.GetPolicyRulesForLinkArgs,
        handler=_get_policy_rules_for_link,
    ),
    "explain_coverage_for_code": ToolDefinition(
        name="explain_coverage_for_code",
        description="Explain coverage evidence for a procedure code.",
        args_model=schemas.ExplainCoverageForCodeArgs,
        handler=_explain_coverage_for_code,
    ),
    "get_bot_capabilities": ToolDefinition(
        name="get_bot_capabilities",
        description="Return a structured list of available tools and capabilities.",
        args_model=schemas.GetBotCapabilitiesArgs,
        handler=_get_bot_capabilities,
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
    "parse_policy_link_and_store": ToolDefinition(
        name="parse_policy_link_and_store",
        description=(
            "Parse a policy link and optionally store extracted rules (requires confirmation)."
        ),
        args_model=schemas.ParsePolicyLinkAndStoreArgs,
        handler=_parse_policy_link_and_store,
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
