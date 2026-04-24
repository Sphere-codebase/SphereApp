"""Virtual claim checklist services."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.id_utils import next_id, next_ids
from app.db.models import (
    ChatSession,
    Claim,
    ClaimDiagnosisCode,
    ClaimMcpCode,
    ClaimProcedureFact,
    DiagnosisCode,
    InsuranceCompany,
    McpCode,
    Patient,
    PatientInsurancePolicy,
    PolicyLink,
    PolicyRule,
    User,
    VirtualClaimDraft,
    VirtualClaimField,
    VirtualClaimQuestion,
)
from app.schemas.virtual_claims import (
    VirtualClaimChecklistResponse,
    VirtualClaimChecklistValue,
    VirtualClaimDiagnosisChecklist,
    VirtualClaimFieldResponse,
    VirtualClaimMaterializeResponse,
    VirtualClaimMissingFieldResponse,
    VirtualClaimPartySummary,
    VirtualClaimPatientChecklist,
    VirtualClaimPayerChecklist,
    VirtualClaimPolicyChecklist,
    VirtualClaimPolicySummaryResponse,
    VirtualClaimProcedureSummary,
    VirtualClaimQuestionResponse,
    VirtualClaimReadinessChecklist,
    VirtualClaimResponse,
    VirtualClaimServiceChecklist,
)
from app.services.claims.normalization import normalize_procedure_code
from app.utils.time import utcnow

SourceType = Literal["database", "user", "llm_extracted", "derived", "policy"]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChecklistFieldDefinition:
    key: str
    label: str
    question: str
    value_type: Literal["string", "bool", "date", "number"] = "string"
    constraint: str | None = None
    keywords: tuple[str, ...] = ()


HEADER_REQUIREMENTS: tuple[ChecklistFieldDefinition, ...] = (
    ChecklistFieldDefinition(
        key="patient_id",
        label="Patient",
        question="Select the patient for this virtual claim.",
    ),
    ChecklistFieldDefinition(
        key="insurance_company_id",
        label="Payer",
        question="Select the payer for this virtual claim.",
    ),
    ChecklistFieldDefinition(
        key="procedure_code",
        label="Procedure code",
        question="Select the procedure code for this virtual claim.",
    ),
)

CHECKLIST_FIELDS: dict[str, ChecklistFieldDefinition] = {
    "insurance.member_id": ChecklistFieldDefinition(
        key="insurance.member_id",
        label="Member ID",
        question="What member ID is on file for this payer?",
    ),
    "insurance.group_number": ChecklistFieldDefinition(
        key="insurance.group_number",
        label="Group number",
        question="What group number applies to this insurance policy?",
    ),
    "insurance.policy_number": ChecklistFieldDefinition(
        key="insurance.policy_number",
        label="Policy number",
        question="What policy number applies to this insurance policy?",
    ),
    "service_date": ChecklistFieldDefinition(
        key="service_date",
        label="Service date",
        question="Provide the planned service date in YYYY-MM-DD format.",
        value_type="date",
    ),
    "service.rendering_provider": ChecklistFieldDefinition(
        key="service.rendering_provider",
        label="Rendering provider",
        question="Who is the rendering provider for this service?",
    ),
    "service.quantity": ChecklistFieldDefinition(
        key="service.quantity",
        label="Quantity",
        question="What quantity or unit count should be billed for this service?",
        value_type="number",
    ),
    "service.modifier": ChecklistFieldDefinition(
        key="service.modifier",
        label="Modifier",
        question="What modifier is required for this service, if any?",
    ),
    "diagnosis.code": ChecklistFieldDefinition(
        key="diagnosis.code",
        label="Diagnosis code",
        question="What diagnosis code supports this claim?",
    ),
    "diagnosis.description": ChecklistFieldDefinition(
        key="diagnosis.description",
        label="Diagnosis description",
        question="What diagnosis description supports this claim?",
    ),
    "clinical.radiculopathy": ChecklistFieldDefinition(
        key="clinical.radiculopathy",
        label="Radiculopathy symptoms",
        question="What dermatomal radiculopathy symptoms are documented?",
        value_type="bool",
        constraint="Document radiculopathy with dermatomal pain or symptoms.",
        keywords=("radiculopathy", "dermatomal", "radicular pain"),
    ),
    "clinical.dermatomal_distribution": ChecklistFieldDefinition(
        key="clinical.dermatomal_distribution",
        label="Dermatomal distribution",
        question="What dermatomal distribution is documented?",
        value_type="bool",
        constraint="Document dermatomal symptom distribution.",
        keywords=("dermatomal", "distribution", "radicular pain"),
    ),
    "clinical.functional_limitation": ChecklistFieldDefinition(
        key="clinical.functional_limitation",
        label="Functional limitation",
        question="What functional limitation is documented?",
        value_type="bool",
        constraint="Document meaningful functional limitation tied to the symptoms.",
        keywords=("functional limitation",),
    ),
    "clinical.conservative_treatment": ChecklistFieldDefinition(
        key="clinical.conservative_treatment",
        label="Conservative treatment failure or intolerance",
        question=(
            "What conservative treatment failed or was not tolerated "
            "(for example physical therapy or non-narcotic analgesics)?"
        ),
        value_type="bool",
        constraint=(
            "Document failed or intolerant conservative treatment such as physical therapy "
            "or non-narcotic analgesics."
        ),
        keywords=("conservative", "physical therapy", "non-narcotic", "analgesic"),
    ),
    "clinical.imaging_guidance": ChecklistFieldDefinition(
        key="clinical.imaging_guidance",
        label="Imaging guidance",
        question="Will fluoroscopy or CT guidance be used?",
        value_type="bool",
        constraint="Use fluoroscopy or CT guidance.",
        keywords=("fluoroscopy", "ct guidance", "imaging guidance"),
    ),
    "clinical.radiology_consistency": ChecklistFieldDefinition(
        key="clinical.radiology_consistency",
        label="Radiologic findings consistent with symptoms",
        question="What radiologic findings are consistent with the symptoms?",
        value_type="bool",
        constraint="Document radicular pain consistent with radiologic findings.",
        keywords=("radiologic findings", "consistent with", "radicular pain"),
    ),
    "clinical.neuro_exam": ChecklistFieldDefinition(
        key="clinical.neuro_exam",
        label="Recent neuro exam findings",
        question="What neuro exam findings within the prior 3 months are documented?",
        value_type="bool",
        constraint=(
            "Document a recent neuro exam with strength loss, altered sensation, "
            "or diminished or asymmetric reflexes."
        ),
        keywords=("neuro exam", "strength loss", "altered sensation", "reflex"),
    ),
    "clinical.mri_or_emg": ChecklistFieldDefinition(
        key="clinical.mri_or_emg",
        label="MRI/CT or EMG/NCV evidence",
        question="What MRI/CT or EMG/NCV evidence of nerve root compression is documented?",
        value_type="bool",
        constraint="Document MRI/CT or EMG/NCV evidence of nerve root compression.",
        keywords=("mri", "emg", "ncv", "nerve root compression", "within prior 12 months"),
    ),
    "treatment.initial_tfesi": ChecklistFieldDefinition(
        key="treatment.initial_tfesi",
        label="Initial therapeutic TFESI",
        question="Is this the initial therapeutic TFESI?",
        value_type="bool",
        constraint="Confirm the treatment context for the TFESI.",
        keywords=("tfesi", "therapeutic"),
    ),
    "utilization.level_limit_ok": ChecklistFieldDefinition(
        key="utilization.level_limit_ok",
        label="Level limits respected",
        question="Are the vertebral level limits respected?",
        value_type="bool",
        constraint="Do not exceed contiguous vertebral level limits.",
        keywords=("contiguous vertebral", "level", "levels"),
    ),
    "utilization.frequency_limit_ok": ChecklistFieldDefinition(
        key="utilization.frequency_limit_ok",
        label="Frequency or session limits respected",
        question="Are the session frequency and annual limits respected?",
        value_type="bool",
        constraint="Respect session frequency, episode, and annual limits.",
        keywords=("session", "frequency", "every two weeks", "annual", "six months", "limit"),
    ),
}

CHECKLIST_EXTERNAL_KEY_MAP = {
    "patient_id": "patient.patient_id",
    "insurance_company_id": "payer_insurance.insurance_company_id",
    "procedure_code": "service.procedure_code",
    "service_date": "service.service_date",
    "diagnosis.code": "diagnosis.diagnosis_code",
    "diagnosis.description": "diagnosis.diagnosis_description",
    "policy.link": "policy_medical_necessity.policy_link_id",
    "policy.rule": "policy_medical_necessity.stored_rules_available",
    "clinical.radiculopathy": "policy_medical_necessity.radiculopathy_evidence",
    "clinical.dermatomal_distribution": "policy_medical_necessity.dermatomal_distribution",
    "clinical.functional_limitation": "policy_medical_necessity.functional_limitation",
    "clinical.conservative_treatment": (
        "policy_medical_necessity.conservative_treatment_failed"
    ),
    "clinical.imaging_guidance": "policy_medical_necessity.imaging_guidance",
    "clinical.radiology_consistency": (
        "policy_medical_necessity.radiologic_findings_consistent"
    ),
    "clinical.neuro_exam": "policy_medical_necessity.neuro_exam_evidence",
    "clinical.mri_or_emg": "policy_medical_necessity.MRI_or_CT_or_EMG_evidence",
    "treatment.initial_tfesi": "policy_medical_necessity.initial_therapeutic_tfesi",
    "utilization.level_limit_ok": "policy_medical_necessity.vertebral_level_limits_respected",
    "utilization.frequency_limit_ok": (
        "policy_medical_necessity.frequency_session_limits_respected"
    ),
}


def get_scoped_chat_session(
    db: Session,
    *,
    session_id: int,
    doctor_id: int,
    clinic_id: int,
) -> ChatSession:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.doctor_id == doctor_id,
            ChatSession.clinic_id == clinic_id,
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def ensure_virtual_claim_draft(db: Session, session: ChatSession) -> VirtualClaimDraft:
    draft = db.execute(
        select(VirtualClaimDraft).where(VirtualClaimDraft.chat_session_id == session.id)
    ).scalar_one_or_none()
    if draft is None:
        draft = VirtualClaimDraft(
            id=next_id(db, VirtualClaimDraft),
            chat_session_id=session.id,
            doctor_id=session.doctor_id,
            clinic_id=session.clinic_id,
            patient_id=session.patient_id,
            materialized_claim_id=session.claim_id,
            status="materialized" if session.claim_id else "open",
            readiness=bool(session.claim_id),
            readiness_reason="Attached to an existing claim." if session.claim_id else None,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(draft)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            draft = db.execute(
                select(VirtualClaimDraft).where(VirtualClaimDraft.chat_session_id == session.id)
            ).scalar_one_or_none()
            if draft is None:
                raise
        else:
            db.refresh(draft)

    if session.claim_id and draft.materialized_claim_id != session.claim_id:
        _seed_virtual_claim_from_claim(db, draft, session.claim_id)
    return draft


def get_virtual_claim_state(
    db: Session,
    *,
    session_id: int,
    doctor_id: int,
    clinic_id: int,
    create_if_missing: bool = True,
) -> VirtualClaimResponse | None:
    session = get_scoped_chat_session(
        db,
        session_id=session_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
    )
    if create_if_missing:
        draft = ensure_virtual_claim_draft(db, session)
    else:
        draft = db.execute(
            select(VirtualClaimDraft).where(VirtualClaimDraft.chat_session_id == session.id)
        ).scalar_one_or_none()
        if draft is None:
            return None
    return recompute_virtual_claim(db, draft)


def update_virtual_claim_state(
    db: Session,
    *,
    session_id: int,
    doctor_id: int,
    clinic_id: int,
    patch: dict[str, Any],
    source_type: Literal["user", "llm_extracted"] = "user",
) -> VirtualClaimResponse:
    session = get_scoped_chat_session(
        db,
        session_id=session_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
    )
    response = bootstrap_virtual_claim_context(
        db,
        session,
        patient_id=patch.get("patient_id"),
        patient_query=_coerce_optional_str(patch.get("patient_query")),
        insurance_company_id=patch.get("insurance_company_id"),
        insurance_company_name=_coerce_optional_str(patch.get("insurance_company_name")),
        procedure_code=_coerce_optional_str(patch.get("procedure_code")),
    )
    draft = ensure_virtual_claim_draft(db, session)
    raw_fields = patch.get("fields") or []
    field_updates: list[tuple[str, Any]] = []
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if isinstance(key, str) and key.strip():
            field_updates.append((key, item.get("value")))
    if field_updates:
        return update_virtual_claim_fields(
            db,
            draft,
            field_updates=field_updates,
            source_type=source_type,
        )
    return response


def recompute_virtual_claim_readiness(state: VirtualClaimResponse) -> dict[str, Any]:
    readiness = state.checklist.readiness
    return {
        "ready_to_draft": readiness.ready_to_draft,
        "missing_fields": readiness.missing_fields,
        "blocking_reasons": readiness.blocking_reasons,
        "next_questions": readiness.next_questions,
    }


def hydrate_virtual_claim_from_tool_result(
    db: Session,
    *,
    session_id: int,
    doctor_id: int,
    clinic_id: int,
    tool_name: str,
    tool_result: dict[str, Any],
) -> VirtualClaimResponse | None:
    if not tool_result or tool_result.get("error"):
        return get_virtual_claim_state(
            db,
            session_id=session_id,
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            create_if_missing=False,
        )

    session = get_scoped_chat_session(
        db,
        session_id=session_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
    )

    if tool_name == "bootstrap_virtual_claim_context":
        return get_virtual_claim_state(
            db,
            session_id=session_id,
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            create_if_missing=False,
        )

    if tool_name == "update_virtual_claim_fields":
        return get_virtual_claim_state(
            db,
            session_id=session_id,
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            create_if_missing=False,
        )

    if tool_name == "get_patient":
        patient = tool_result.get("patient") or {}
        patient_id = patient.get("id")
        if isinstance(patient_id, int):
            return bootstrap_virtual_claim_context(db, session, patient_id=patient_id)

    if tool_name == "get_claim":
        claim = tool_result.get("claim") or {}
        claim_id = claim.get("id")
        patient_id = claim.get("patient_id")
        insurance_company_id = claim.get("insurance_company_id")
        changed = False
        if isinstance(claim_id, int) and session.claim_id != claim_id:
            session.claim_id = claim_id
            changed = True
        if isinstance(patient_id, int) and session.patient_id != patient_id:
            session.patient_id = patient_id
            changed = True
        if changed:
            db.add(session)
            db.commit()
        bootstrap_virtual_claim_context(
            db,
            session,
            patient_id=patient_id if isinstance(patient_id, int) else None,
            insurance_company_id=insurance_company_id
            if isinstance(insurance_company_id, int)
            else None,
        )
        draft = ensure_virtual_claim_draft(db, session)
        if isinstance(claim_id, int) and draft.materialized_claim_id != claim_id:
            _seed_virtual_claim_from_claim(db, draft, claim_id)
        return recompute_virtual_claim(db, draft)

    if tool_name == "get_procedure_code" and tool_result.get("exists") is True:
        code = tool_result.get("code")
        if isinstance(code, str) and code.strip():
            return bootstrap_virtual_claim_context(db, session, procedure_code=code.strip())

    if tool_name == "explain_coverage_for_code":
        code = tool_result.get("code")
        if isinstance(code, str) and code.strip():
            return bootstrap_virtual_claim_context(db, session, procedure_code=code.strip())

    if tool_name == "list_policy_links_for_code":
        draft = ensure_virtual_claim_draft(db, session)
        links = tool_result.get("links") or []
        if isinstance(links, list) and draft.insurance_company_id is not None:
            selected = next(
                (
                    item
                    for item in links
                    if isinstance(item, dict)
                    and item.get("insurance_company_id") == draft.insurance_company_id
                ),
                None,
            )
            if selected and isinstance(selected.get("policy_link_id"), int):
                draft.selected_policy_link_id = selected["policy_link_id"]
                draft.updated_at = utcnow()
                db.add(draft)
                db.commit()
        return recompute_virtual_claim(db, draft)

    if tool_name == "get_policy_rules_for_link":
        draft = ensure_virtual_claim_draft(db, session)
        policy_link_id = tool_result.get("policy_link_id")
        if isinstance(policy_link_id, int):
            draft.selected_policy_link_id = policy_link_id
            selected_rule = (
                db.execute(
                    select(PolicyRule)
                    .where(PolicyRule.policy_link_id == policy_link_id)
                    .order_by(PolicyRule.extracted_at.desc())
                )
                .scalars()
                .first()
            )
            draft.selected_policy_rule_id = selected_rule.id if selected_rule else None
            draft.updated_at = utcnow()
            db.add(draft)
            db.commit()
        return recompute_virtual_claim(db, draft)

    return get_virtual_claim_state(
        db,
        session_id=session_id,
        doctor_id=doctor_id,
        clinic_id=clinic_id,
        create_if_missing=False,
    )


def bootstrap_virtual_claim_context(
    db: Session,
    session: ChatSession,
    *,
    patient_id: int | str | None = None,
    patient_query: str | None = None,
    insurance_company_id: int | str | None = None,
    insurance_company_name: str | None = None,
    procedure_code: str | None = None,
) -> VirtualClaimResponse:
    draft = ensure_virtual_claim_draft(db, session)
    draft = _lock_virtual_claim_draft(db, draft.id)
    changed = False

    resolved_patient_id = _coerce_optional_int(patient_id)
    if resolved_patient_id is None and patient_query:
        resolved_patient_id = _resolve_patient_id_from_query(
            db,
            clinic_id=session.clinic_id,
            patient_query=patient_query,
        )
    if resolved_patient_id is not None:
        patient = db.execute(
            select(Patient).where(
                Patient.id == resolved_patient_id,
                Patient.clinic_id == session.clinic_id,
            )
        ).scalar_one_or_none()
        if patient is not None and draft.patient_id != patient.id:
            draft.patient_id = patient.id
            session.patient_id = patient.id
            changed = True

    resolved_company_id = _resolve_insurance_company_id(
        db,
        insurance_company_id=insurance_company_id,
        insurance_company_name=insurance_company_name,
    )
    if resolved_company_id is not None:
        if draft.insurance_company_id != resolved_company_id:
            draft.insurance_company_id = resolved_company_id
            changed = True

    if procedure_code is not None:
        normalized_code = normalize_procedure_code(procedure_code)
        mcp = (
            db.execute(select(McpCode).where(McpCode.code == normalized_code)).scalar_one_or_none()
            if normalized_code is not None
            else None
        )
        if mcp is not None:
            if draft.procedure_code != mcp.code:
                draft.procedure_code = mcp.code
                changed = True

    if changed:
        draft.updated_at = utcnow()
        db.add_all([draft, session])
        db.commit()

    return recompute_virtual_claim(db, draft)


def update_virtual_claim_fields(
    db: Session,
    draft: VirtualClaimDraft,
    *,
    field_updates: list[tuple[str, Any]],
    source_type: Literal["user", "llm_extracted"] = "user",
) -> VirtualClaimResponse:
    draft = _lock_virtual_claim_draft(db, draft.id)
    unique_keys = list(dict.fromkeys(key for key, _raw_value in field_updates))
    persisted_field_keys = set(
        db.execute(
            select(VirtualClaimField.field_key).where(
                VirtualClaimField.draft_id == draft.id,
                VirtualClaimField.field_key.in_(unique_keys),
            )
        ).scalars()
    )
    pending_field_keys = {field.field_key for field in draft.fields}
    keys_requiring_ids = [
        key
        for key in unique_keys
        if key not in persisted_field_keys and key not in pending_field_keys
    ]
    allocated_field_ids = dict(
        zip(
            keys_requiring_ids,
            next_ids(db, VirtualClaimField, len(keys_requiring_ids)),
            strict=False,
        )
    )

    for key, raw_value in field_updates:
        definition = CHECKLIST_FIELDS.get(key)
        if definition is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported virtual claim field: {key}",
            )
        normalized_value, field_status = _normalize_field_value(definition, raw_value)
        set_virtual_claim_field(
            db,
            draft,
            key=key,
            value=normalized_value,
            status=field_status,
            source_type=source_type,
            source_ref_json=None,
            allocated_id=allocated_field_ids.get(key),
        )

    draft.updated_at = utcnow()
    db.add(draft)
    db.commit()
    return recompute_virtual_claim(db, draft)


def recompute_virtual_claim(db: Session, draft: VirtualClaimDraft) -> VirtualClaimResponse:
    started = time.monotonic()
    draft = _lock_virtual_claim_draft(db, draft.id)
    hydrate_virtual_claim_from_records(db, draft)
    patient = db.get(Patient, draft.patient_id) if draft.patient_id else None
    payer = (
        db.get(InsuranceCompany, draft.insurance_company_id)
        if draft.insurance_company_id
        else None
    )
    doctor = db.get(User, draft.doctor_id) if draft.doctor_id else None
    procedure = (
        db.execute(select(McpCode).where(McpCode.code == draft.procedure_code)).scalar_one_or_none()
        if draft.procedure_code
        else None
    )
    patient_policy = _get_patient_policy(
        db,
        patient_id=draft.patient_id,
        insurance_company_id=draft.insurance_company_id,
    )
    procedure_fact = _get_claim_procedure_fact(
        db,
        claim_id=draft.materialized_claim_id,
        procedure_code=draft.procedure_code,
    )

    selected_link, selected_rule = _sync_policy_references(db, draft)

    field_map = {field.field_key: field for field in draft.fields}
    missing_fields: list[VirtualClaimMissingFieldResponse] = []
    follow_up_questions: list[VirtualClaimQuestionResponse] = []
    filled: list[VirtualClaimFieldResponse] = []
    missing: list[VirtualClaimFieldResponse] = []
    needs_review: list[VirtualClaimFieldResponse] = []
    policy_constraints: list[VirtualClaimFieldResponse] = []

    for definition in HEADER_REQUIREMENTS:
        field_response, missing_item = _evaluate_header_requirement(
            definition,
            draft=draft,
            patient=patient,
            payer=payer,
            procedure=procedure,
        )
        if field_response.status == "present":
            filled.append(field_response)
        elif field_response.status == "needs_review":
            needs_review.append(field_response)
        else:
            missing.append(field_response)
            if missing_item is not None:
                missing_fields.append(missing_item)

    service_date_definition = CHECKLIST_FIELDS["service_date"]
    service_date_response, service_missing = _evaluate_stored_requirement(
        service_date_definition,
        field_map.get(service_date_definition.key),
    )
    if service_date_response.status == "present":
        filled.append(service_date_response)
    elif service_date_response.status == "needs_review":
        needs_review.append(service_date_response)
    else:
        missing.append(service_date_response)
        missing_fields.append(service_missing)

    active_policy_definitions = _active_policy_definitions(selected_rule)
    if draft.procedure_code:
        diagnosis_definition = CHECKLIST_FIELDS["diagnosis.code"]
        if diagnosis_definition not in active_policy_definitions:
            active_policy_definitions = [diagnosis_definition, *active_policy_definitions]

    if draft.procedure_code and draft.insurance_company_id and selected_link is None:
        missing_fields.append(
            VirtualClaimMissingFieldResponse(
                key="policy.link",
                label="Stored policy link",
                question="Stored payer policy link is missing for this procedure code.",
            )
        )
        missing.append(
            VirtualClaimFieldResponse(
                key="policy.link",
                label="Stored policy link",
                status="missing",
                value=None,
                source_type="policy",
            )
        )

    if selected_link is not None and selected_rule is None:
        missing_fields.append(
            VirtualClaimMissingFieldResponse(
                key="policy.rule",
                label="Stored policy rule",
                question="Stored payer policy rule is missing for the selected policy link.",
            )
        )
        missing.append(
            VirtualClaimFieldResponse(
                key="policy.rule",
                label="Stored policy rule",
                status="missing",
                value=None,
                source_type="policy",
            )
        )

    for definition in active_policy_definitions:
        policy_constraints.append(
            VirtualClaimFieldResponse(
                key=f"policy.{definition.key}",
                label=definition.label,
                status="derived",
                value=definition.constraint,
                source_type="policy",
            )
        )
        if definition.key == "service_date":
            continue
        field_response, missing_item = _evaluate_stored_requirement(
            definition,
            field_map.get(definition.key),
        )
        if field_response.status == "present":
            filled.append(field_response)
        elif field_response.status == "needs_review":
            needs_review.append(field_response)
        else:
            missing.append(field_response)
            missing_fields.append(missing_item)

    deduped_filled = _dedupe_fields(filled)
    deduped_missing = _dedupe_fields(missing)
    deduped_needs_review = _dedupe_fields(needs_review)
    deduped_missing_fields = _dedupe_missing_fields(missing_fields)

    for item in deduped_missing_fields:
        follow_up_questions.append(
            VirtualClaimQuestionResponse(
                question_key=item.key,
                prompt=item.question,
                status="open",
                answer=None,
            )
        )

    existing_questions = _list_virtual_claim_questions(db, draft)
    existing_questions_by_key: dict[str, VirtualClaimQuestion] = {}
    for question in existing_questions:
        retained = existing_questions_by_key.setdefault(question.question_key, question)
        if retained is not question:
            db.delete(question)

    desired_question_keys = [question.question_key for question in follow_up_questions]
    question_ids = iter(
        next_ids(
            db,
            VirtualClaimQuestion,
            sum(1 for key in desired_question_keys if key not in existing_questions_by_key),
        )
    )
    for question in follow_up_questions:
        set_virtual_claim_question(
            db,
            draft,
            question_key=question.question_key,
            prompt=question.prompt,
            status=question.status,
            answer_json=question.answer,
            existing=existing_questions_by_key.pop(question.question_key, None),
            allocated_id=next(question_ids, None),
        )
    for stale_question in existing_questions_by_key.values():
        db.delete(stale_question)

    if draft.materialized_claim_id is not None:
        draft.status = "materialized"
        draft.readiness = True
        draft.readiness_reason = "Materialized as a real claim."
    else:
        draft.readiness = not deduped_missing and not deduped_needs_review
        draft.status = "ready" if draft.readiness else "open"
        if draft.readiness:
            draft.readiness_reason = "Checklist is complete and ready to draft."
        elif deduped_needs_review:
            draft.readiness_reason = "Checklist has conflicting or non-compliant fields."
        else:
            draft.readiness_reason = "Checklist is missing required fields."
    draft.updated_at = utcnow()

    db.add(draft)
    db.commit()
    db.refresh(draft)

    checklist = _build_structured_checklist(
        draft=draft,
        patient=patient,
        payer=payer,
        patient_policy=patient_policy,
        doctor=doctor,
        procedure=procedure,
        procedure_fact=procedure_fact,
        selected_link=selected_link,
        selected_rule=selected_rule,
        field_map=field_map,
        missing_fields=deduped_missing_fields,
        follow_up_questions=follow_up_questions,
    )

    response = VirtualClaimResponse(
        draft_id=draft.id,
        session_id=draft.chat_session_id,
        status=draft.status,  # type: ignore[arg-type]
        readiness=draft.readiness,
        readiness_reason=draft.readiness_reason,
        patient=VirtualClaimPartySummary(
            id=patient.id if patient else None,
            name=_patient_name(patient),
            date_of_birth=patient.date_of_birth.isoformat()
            if patient and patient.date_of_birth
            else None,
        )
        if patient
        else None,
        payer=VirtualClaimPartySummary(
            id=payer.id if payer else None,
            name=payer.name if payer else None,
        )
        if payer
        else None,
        procedure=VirtualClaimProcedureSummary(
            code=procedure.code if procedure else draft.procedure_code,
            description=procedure.description if procedure else None,
        )
        if procedure or draft.procedure_code
        else None,
        materialized_claim_id=draft.materialized_claim_id,
        policy_summary=_policy_summary_response(selected_link, selected_rule),
        checklist=checklist,
        filled=deduped_filled,
        missing=deduped_missing,
        needs_review=deduped_needs_review,
        policy_constraints=_dedupe_fields(policy_constraints),
        missing_fields=deduped_missing_fields,
        follow_up_questions=follow_up_questions,
        updated_at=draft.updated_at,
    )
    logger.info(
        "virtual_claim_recompute draft_id=%s session_id=%s duration_ms=%s missing=%s ready=%s",
        draft.id,
        draft.chat_session_id,
        round((time.monotonic() - started) * 1000, 2),
        len(response.missing_fields),
        response.checklist.readiness.ready_to_draft,
    )
    return response


def list_missing_virtual_claim_fields(db: Session, draft: VirtualClaimDraft) -> dict[str, Any]:
    response = recompute_virtual_claim(db, draft)
    return {
        "draft_id": response.draft_id,
        "readiness": response.readiness,
        "readiness_reason": response.readiness_reason,
        "virtual_claim": response.model_dump(mode="json"),
        "missing_fields": [item.model_dump(mode="json") for item in response.missing_fields],
        "follow_up_questions": [
            item.model_dump(mode="json") for item in response.follow_up_questions
        ],
    }


def explain_virtual_claim_policy(db: Session, draft: VirtualClaimDraft) -> dict[str, Any]:
    response = recompute_virtual_claim(db, draft)
    return {
        "draft_id": response.draft_id,
        "virtual_claim": response.model_dump(mode="json"),
        "patient": response.patient.model_dump(mode="json") if response.patient else None,
        "payer": response.payer.model_dump(mode="json") if response.payer else None,
        "procedure": response.procedure.model_dump(mode="json") if response.procedure else None,
        "policy_summary": response.policy_summary.model_dump(mode="json")
        if response.policy_summary
        else None,
        "policy_constraints": [
            item.model_dump(mode="json") for item in response.policy_constraints
        ],
        "missing_information": [item.model_dump(mode="json") for item in response.missing_fields],
        "answer_hint": (
            "Use only stored policy rules linked to the current virtual claim. "
            "Separate database-backed rules from missing checklist facts."
        ),
    }


def materialize_virtual_claim(
    db: Session,
    *,
    session: ChatSession,
    draft: VirtualClaimDraft,
    confirm: bool = False,
) -> VirtualClaimMaterializeResponse:
    response = recompute_virtual_claim(db, draft)
    if response.materialized_claim_id is not None:
        return VirtualClaimMaterializeResponse(
            action_required=False,
            claim_id=response.materialized_claim_id,
            draft=response,
        )
    if not response.readiness:
        return VirtualClaimMaterializeResponse(
            action_required=False,
            claim_id=None,
            draft=response,
        )

    claim_payload = {
        "patient_id": draft.patient_id,
        "insurance_company_id": draft.insurance_company_id,
        "service_date": _field_value(draft, "service_date"),
        "procedure_code": draft.procedure_code,
        "diagnosis_code": _field_value(draft, "diagnosis.code"),
    }
    proposal = {
        "draft_id": draft.id,
        "session_id": draft.chat_session_id,
        "summary": {
            "patient_name": response.patient.name if response.patient else None,
            "payer_name": response.payer.name if response.payer else None,
            "procedure_code": response.procedure.code if response.procedure else None,
            "service_date": claim_payload["service_date"],
        },
        "claim_payload": claim_payload,
    }
    if not confirm:
        return VirtualClaimMaterializeResponse(
            action_required=True,
            proposal=proposal,
            claim_id=None,
            draft=response,
        )

    if draft.patient_id is None or draft.insurance_company_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Virtual claim is missing patient or payer context",
        )

    claim = Claim(
        id=next_id(db, Claim),
        doctor_id=session.doctor_id,
        clinic_id=session.clinic_id,
        patient_id=draft.patient_id,
        insurance_company_id=draft.insurance_company_id,
        claim_status="DRAFT",
        service_date=_coerce_iso_date(_field_value(draft, "service_date")),
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(claim)
    db.flush()

    if draft.procedure_code:
        db.add(ClaimMcpCode(claim_id=claim.id, mcp_code=draft.procedure_code))
    diagnosis_code = _field_value(draft, "diagnosis.code")
    if isinstance(diagnosis_code, str) and diagnosis_code.strip():
        diagnosis = db.execute(
            select(DiagnosisCode).where(DiagnosisCode.code == diagnosis_code)
        ).scalar_one_or_none()
        if diagnosis is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Diagnosis code not found",
            )
        db.add(ClaimDiagnosisCode(claim_id=claim.id, diagnosis_code=diagnosis_code))

    draft.materialized_claim_id = claim.id
    draft.status = "materialized"
    draft.readiness = True
    draft.readiness_reason = "Materialized as a real claim."
    draft.updated_at = utcnow()
    session.claim_id = claim.id
    session.patient_id = claim.patient_id

    db.add_all([draft, session, claim])
    db.commit()
    db.refresh(draft)

    return VirtualClaimMaterializeResponse(
        action_required=False,
        proposal=proposal,
        claim_id=claim.id,
        draft=recompute_virtual_claim(db, draft),
    )


def _seed_virtual_claim_from_claim(db: Session, draft: VirtualClaimDraft, claim_id: int) -> None:
    draft = _lock_virtual_claim_draft(db, draft.id)
    claim = db.execute(select(Claim).where(Claim.id == claim_id)).scalar_one_or_none()
    if claim is None:
        return
    draft.patient_id = claim.patient_id
    draft.insurance_company_id = claim.insurance_company_id
    draft.materialized_claim_id = claim.id
    draft.status = "materialized"
    draft.readiness = True
    draft.readiness_reason = "Attached to an existing claim."

    mcp_code = (
        db.execute(select(ClaimMcpCode.mcp_code).where(ClaimMcpCode.claim_id == claim.id))
        .scalars()
        .first()
    )
    if mcp_code:
        draft.procedure_code = mcp_code

    set_virtual_claim_field(
        db,
        draft,
        key="service_date",
        value=claim.service_date.isoformat() if claim.service_date else None,
        status="present" if claim.service_date else "missing",
        source_type="database",
        source_ref_json=None,
    )

    diagnosis_code = (
        db.execute(
            select(ClaimDiagnosisCode.diagnosis_code).where(ClaimDiagnosisCode.claim_id == claim.id)
        )
        .scalars()
        .first()
    )
    if diagnosis_code:
        set_virtual_claim_field(
            db,
            draft,
            key="diagnosis.code",
            value=diagnosis_code,
            status="present",
            source_type="database",
            source_ref_json=None,
        )

    draft.updated_at = utcnow()
    db.add(draft)
    db.commit()


def _policy_summary_response(
    selected_link: PolicyLink | None,
    selected_rule: PolicyRule | None,
) -> VirtualClaimPolicySummaryResponse | None:
    if selected_link is None and selected_rule is None:
        return None
    return VirtualClaimPolicySummaryResponse(
        policy_link_id=selected_link.id if selected_link else None,
        policy_rule_id=selected_rule.id if selected_rule else None,
        policy_url=selected_link.policy_url if selected_link else None,
        title=selected_rule.title if selected_rule else None,
        extracted_at=selected_rule.extracted_at if selected_rule else None,
        rules_json=_parse_rule_payload(selected_rule.rules_json) if selected_rule else None,
        criteria_json=selected_rule.criteria_json if selected_rule else None,
        notes_json=selected_rule.notes_json if selected_rule else None,
    )


def hydrate_virtual_claim_from_records(db: Session, draft: VirtualClaimDraft) -> None:
    patient = db.get(Patient, draft.patient_id) if draft.patient_id else None
    doctor = db.get(User, draft.doctor_id) if draft.doctor_id else None
    patient_policy = _get_patient_policy(
        db,
        patient_id=draft.patient_id,
        insurance_company_id=draft.insurance_company_id,
    )
    procedure_fact = _get_claim_procedure_fact(
        db,
        claim_id=draft.materialized_claim_id,
        procedure_code=draft.procedure_code,
    )

    if patient_policy and patient_policy.member_id:
        _set_database_field(db, draft, "insurance.member_id", patient_policy.member_id)
    if patient and patient.provider_name:
        _set_database_field(db, draft, "service.rendering_provider", patient.provider_name)
    elif doctor and doctor.full_name:
        _set_database_field(db, draft, "service.rendering_provider", doctor.full_name)
    if procedure_fact and procedure_fact.units is not None:
        _set_database_field(db, draft, "service.quantity", float(procedure_fact.units))
    if procedure_fact and procedure_fact.modifier:
        _set_database_field(db, draft, "service.modifier", procedure_fact.modifier)
    diagnosis_code = _field_value(draft, "diagnosis.code")
    if isinstance(diagnosis_code, str) and diagnosis_code.strip():
        diagnosis = db.execute(
            select(DiagnosisCode).where(DiagnosisCode.code == diagnosis_code.strip().upper())
        ).scalar_one_or_none()
        if diagnosis and diagnosis.description:
            _set_database_field(db, draft, "diagnosis.description", diagnosis.description)


def _build_structured_checklist(
    *,
    draft: VirtualClaimDraft,
    patient: Patient | None,
    payer: InsuranceCompany | None,
    patient_policy: PatientInsurancePolicy | None,
    doctor: User | None,
    procedure: McpCode | None,
    procedure_fact: ClaimProcedureFact | None,
    selected_link: PolicyLink | None,
    selected_rule: PolicyRule | None,
    field_map: dict[str, VirtualClaimField],
    missing_fields: list[VirtualClaimMissingFieldResponse],
    follow_up_questions: list[VirtualClaimQuestionResponse],
) -> VirtualClaimChecklistResponse:
    patient_section = VirtualClaimPatientChecklist(
        patient_id=_value_from_direct(
            label="Patient ID",
            value=patient.id if patient else draft.patient_id,
            source_type="database" if patient else "database",
        ),
        first_name=_value_from_direct(
            label="First name",
            value=patient.first_name if patient else None,
            source_type="database",
        ),
        last_name=_value_from_direct(
            label="Last name",
            value=patient.last_name if patient else None,
            source_type="database",
        ),
        date_of_birth=_value_from_direct(
            label="Date of birth",
            value=patient.date_of_birth.isoformat() if patient and patient.date_of_birth else None,
            source_type="database",
        ),
    )

    payer_section = VirtualClaimPayerChecklist(
        insurance_company_id=_value_from_direct(
            label="Insurance company ID",
            value=payer.id if payer else draft.insurance_company_id,
            source_type="database",
        ),
        payer_name=_value_from_direct(
            label="Payer name",
            value=payer.name if payer else None,
            source_type="database",
        ),
        member_id=_value_from_field(
            label="Member ID",
            field=field_map.get("insurance.member_id"),
            required=False,
        ),
        group_number=_value_from_field(
            label="Group number",
            field=field_map.get("insurance.group_number"),
            required=False,
        ),
        policy_number=_value_from_field(
            label="Policy number",
            field=field_map.get("insurance.policy_number"),
            required=False,
        ),
    )

    quantity_value = field_map.get("service.quantity")
    if quantity_value is None and procedure_fact and procedure_fact.units is not None:
        quantity_value = _ephemeral_field(
            "service.quantity",
            float(procedure_fact.units),
            "present",
            "database",
        )
    modifier_value = field_map.get("service.modifier")
    if modifier_value is None and procedure_fact and procedure_fact.modifier:
        modifier_value = _ephemeral_field(
            "service.modifier",
            procedure_fact.modifier,
            "present",
            "database",
        )
    rendering_provider_field = field_map.get("service.rendering_provider")
    if rendering_provider_field is None:
        provider_name = patient.provider_name if patient and patient.provider_name else None
        if provider_name is None and doctor and doctor.full_name:
            provider_name = doctor.full_name
        if provider_name:
            rendering_provider_field = _ephemeral_field(
                "service.rendering_provider",
                provider_name,
                "present",
                "database",
            )

    service_section = VirtualClaimServiceChecklist(
        procedure_code=_value_from_direct(
            label="Procedure code",
            value=procedure.code if procedure else draft.procedure_code,
            source_type="database" if procedure else "database",
        ),
        procedure_description=_value_from_direct(
            label="Procedure description",
            value=procedure.description if procedure else None,
            source_type="database",
        ),
        service_date=_value_from_field(
            label="Service date",
            field=field_map.get("service_date"),
        ),
        rendering_provider=_value_from_field(
            label="Rendering provider",
            field=rendering_provider_field,
            required=False,
        ),
        quantity=_value_from_field(
            label="Quantity",
            field=quantity_value,
            required=False,
        ),
        modifier=_value_from_field(
            label="Modifier",
            field=modifier_value,
            required=False,
        ),
    )

    diagnosis_section = VirtualClaimDiagnosisChecklist(
        diagnosis_code=_value_from_field(
            label="Diagnosis code",
            field=field_map.get("diagnosis.code"),
        ),
        diagnosis_description=_value_from_field(
            label="Diagnosis description",
            field=field_map.get("diagnosis.description"),
            required=False,
        ),
    )

    radiculopathy_field = field_map.get("clinical.radiculopathy")
    dermatomal_field = field_map.get("clinical.dermatomal_distribution") or radiculopathy_field
    policy_section = VirtualClaimPolicyChecklist(
        policy_link_id=_value_from_direct(
            label="Policy link ID",
            value=selected_link.id if selected_link else None,
            source_type="policy",
        ),
        policy_url=_value_from_direct(
            label="Policy URL",
            value=selected_link.policy_url if selected_link else None,
            source_type="policy",
        ),
        stored_rules_available=_value_from_direct(
            label="Stored rules available",
            value=True if selected_rule else None,
            source_type="policy",
        ),
        radiculopathy_evidence=_value_from_field(
            label="Radiculopathy evidence",
            field=radiculopathy_field,
        ),
        dermatomal_distribution=_value_from_field(
            label="Dermatomal distribution",
            field=dermatomal_field,
        ),
        functional_limitation=_value_from_field(
            label="Functional limitation",
            field=field_map.get("clinical.functional_limitation"),
        ),
        conservative_treatment_failed=_value_from_field(
            label="Conservative treatment failed",
            field=field_map.get("clinical.conservative_treatment"),
        ),
        imaging_guidance=_value_from_field(
            label="Imaging guidance",
            field=field_map.get("clinical.imaging_guidance"),
        ),
        MRI_or_CT_or_EMG_evidence=_value_from_field(
            label="MRI, CT, or EMG evidence",
            field=field_map.get("clinical.mri_or_emg"),
        ),
        neuro_exam_evidence=_value_from_field(
            label="Neuro exam evidence",
            field=field_map.get("clinical.neuro_exam"),
        ),
        frequency_session_limits_respected=_value_from_field(
            label="Frequency and session limits respected",
            field=field_map.get("utilization.frequency_limit_ok"),
        ),
        radiologic_findings_consistent=_value_from_field(
            label="Radiologic findings consistent with symptoms",
            field=field_map.get("clinical.radiology_consistency"),
            required=False,
        ),
        initial_therapeutic_tfesi=_value_from_field(
            label="Initial therapeutic TFESI",
            field=field_map.get("treatment.initial_tfesi"),
            required=False,
        ),
        vertebral_level_limits_respected=_value_from_field(
            label="Vertebral level limits respected",
            field=field_map.get("utilization.level_limit_ok"),
            required=False,
        ),
    )

    readiness_section = VirtualClaimReadinessChecklist(
        ready_to_draft=draft.readiness,
        missing_fields=[
            CHECKLIST_EXTERNAL_KEY_MAP.get(item.key, item.key) for item in missing_fields
        ],
        blocking_reasons=_blocking_reasons(missing_fields, draft),
        next_questions=[item.prompt for item in follow_up_questions],
    )

    return VirtualClaimChecklistResponse(
        patient=patient_section,
        payer_insurance=payer_section,
        service=service_section,
        diagnosis=diagnosis_section,
        policy_medical_necessity=policy_section,
        readiness=readiness_section,
    )


def _blocking_reasons(
    missing_fields: list[VirtualClaimMissingFieldResponse],
    draft: VirtualClaimDraft,
) -> list[str]:
    reasons: list[str] = []
    for item in missing_fields:
        rendered = CHECKLIST_EXTERNAL_KEY_MAP.get(item.key, item.label)
        reasons.append(f"{rendered}: {item.question}")
    if not draft.readiness and draft.readiness_reason and draft.readiness_reason not in reasons:
        reasons.insert(0, draft.readiness_reason)
    return reasons


def _value_from_direct(
    *,
    label: str,
    value: Any,
    source_type: SourceType,
    required: bool = True,
) -> VirtualClaimChecklistValue:
    if _is_blank(value):
        return VirtualClaimChecklistValue(
            value=None,
            status="missing",
            source_type=source_type,
            required=required,
            label=label,
        )
    return VirtualClaimChecklistValue(
        value=value,
        status="present" if source_type != "policy" else "derived",
        source_type=source_type,
        required=required,
        label=label,
    )


def _value_from_field(
    *,
    label: str,
    field: VirtualClaimField | None,
    required: bool = True,
) -> VirtualClaimChecklistValue:
    if field is None or field.status == "missing" or _is_blank(field.value_json):
        return VirtualClaimChecklistValue(
            value=None,
            status="missing",
            source_type=field.source_type if field else "user",
            required=required,
            label=label,
        )
    return VirtualClaimChecklistValue(
        value=field.value_json,
        status=field.status,  # type: ignore[arg-type]
        source_type=field.source_type,  # type: ignore[arg-type]
        required=required,
        label=label,
    )


def _ephemeral_field(
    key: str,
    value: Any,
    status: str,
    source_type: str,
) -> VirtualClaimField:
    return VirtualClaimField(
        id=0,
        draft_id=0,
        clinic_id=0,
        field_key=key,
        value_json=value,
        status=status,
        source_type=source_type,
    )


def _get_patient_policy(
    db: Session,
    *,
    patient_id: int | None,
    insurance_company_id: int | None,
) -> PatientInsurancePolicy | None:
    if patient_id is None:
        return None
    stmt = select(PatientInsurancePolicy).where(PatientInsurancePolicy.patient_id == patient_id)
    if insurance_company_id is not None:
        stmt = stmt.where(PatientInsurancePolicy.insurance_company_id == insurance_company_id)
    return (
        db.execute(
            stmt.order_by(
                PatientInsurancePolicy.priority.asc(),
                PatientInsurancePolicy.id.asc(),
            )
        )
        .scalars()
        .first()
    )


def _get_claim_procedure_fact(
    db: Session,
    *,
    claim_id: int | None,
    procedure_code: str | None,
) -> ClaimProcedureFact | None:
    if claim_id is None:
        return None
    stmt = select(ClaimProcedureFact).where(ClaimProcedureFact.claim_id == claim_id)
    if procedure_code:
        stmt = stmt.where(ClaimProcedureFact.mcp_code == procedure_code)
    return db.execute(stmt.order_by(ClaimProcedureFact.id.asc())).scalars().first()


def _set_database_field(db: Session, draft: VirtualClaimDraft, key: str, value: Any) -> None:
    definition = CHECKLIST_FIELDS.get(key)
    if definition is None:
        return
    normalized_value, field_status = _normalize_field_value(definition, value)
    field = _find_virtual_claim_field(db, draft, key)
    if (
        field is not None
        and field.source_type == "database"
        and field.value_json == normalized_value
        and field.status == field_status
    ):
        return
    if (
        field is not None
        and field.source_type not in {"database", "derived"}
        and not _is_blank(field.value_json)
    ):
        return
    set_virtual_claim_field(
        db,
        draft,
        key=key,
        value=normalized_value,
        status=field_status,
        source_type="database",
        source_ref_json=None,
        existing=field,
    )


def _sync_policy_references(
    db: Session,
    draft: VirtualClaimDraft,
) -> tuple[PolicyLink | None, PolicyRule | None]:
    selected_link = None
    selected_rule = None
    if draft.insurance_company_id and draft.procedure_code:
        selected_link = (
            db.execute(
                select(PolicyLink)
                .where(
                    PolicyLink.insurance_company_id == draft.insurance_company_id,
                    PolicyLink.mcp_code == draft.procedure_code,
                )
                .order_by(PolicyLink.id.asc())
            )
            .scalars()
            .first()
        )
        if selected_link is not None:
            selected_rule = (
                db.execute(
                    select(PolicyRule)
                    .where(PolicyRule.policy_link_id == selected_link.id)
                    .order_by(PolicyRule.extracted_at.desc())
                )
                .scalars()
                .first()
            )
    draft.selected_policy_link_id = selected_link.id if selected_link else None
    draft.selected_policy_rule_id = selected_rule.id if selected_rule else None
    return selected_link, selected_rule


def _active_policy_definitions(selected_rule: PolicyRule | None) -> list[ChecklistFieldDefinition]:
    if selected_rule is None:
        return []
    haystack = _policy_text(selected_rule)
    active: list[ChecklistFieldDefinition] = []
    for definition in CHECKLIST_FIELDS.values():
        if not definition.key.startswith(("clinical.", "treatment.", "utilization.")):
            continue
        if any(keyword in haystack for keyword in definition.keywords):
            active.append(definition)
    return active


def _policy_text(rule: PolicyRule) -> str:
    chunks = [rule.title or ""]
    chunks.append(_json_to_text(_parse_rule_payload(rule.rules_json)))
    chunks.append(_json_to_text(rule.criteria_json))
    chunks.append(_json_to_text(rule.notes_json))
    return " ".join(chunk.lower() for chunk in chunks if chunk)


def _json_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except TypeError:
        return str(value)


def _parse_rule_payload(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _evaluate_header_requirement(
    definition: ChecklistFieldDefinition,
    *,
    draft: VirtualClaimDraft,
    patient: Patient | None,
    payer: InsuranceCompany | None,
    procedure: McpCode | None,
) -> tuple[VirtualClaimFieldResponse, VirtualClaimMissingFieldResponse | None]:
    if definition.key == "patient_id":
        if patient is not None:
            return (
                VirtualClaimFieldResponse(
                    key=definition.key,
                    label=definition.label,
                    status="present",
                    value=_patient_name(patient),
                    source_type="database",
                ),
                None,
            )
    elif definition.key == "insurance_company_id":
        if payer is not None:
            return (
                VirtualClaimFieldResponse(
                    key=definition.key,
                    label=definition.label,
                    status="present",
                    value=payer.name,
                    source_type="database",
                ),
                None,
            )
    elif definition.key == "procedure_code":
        if draft.procedure_code and procedure is not None:
            return (
                VirtualClaimFieldResponse(
                    key=definition.key,
                    label=definition.label,
                    status="present",
                    value=f"{procedure.code} - {procedure.description}",
                    source_type="database",
                ),
                None,
            )
        if draft.procedure_code:
            return (
                VirtualClaimFieldResponse(
                    key=definition.key,
                    label=definition.label,
                    status="needs_review",
                    value=draft.procedure_code,
                    source_type="user",
                ),
                None,
            )

    return (
        VirtualClaimFieldResponse(
            key=definition.key,
            label=definition.label,
            status="missing",
            value=None,
            source_type="database",
        ),
        VirtualClaimMissingFieldResponse(
            key=definition.key,
            label=definition.label,
            question=definition.question,
        ),
    )


def _evaluate_stored_requirement(
    definition: ChecklistFieldDefinition,
    field: VirtualClaimField | None,
) -> tuple[VirtualClaimFieldResponse, VirtualClaimMissingFieldResponse]:
    if field is None or field.status == "missing" or _is_blank(field.value_json):
        return (
            VirtualClaimFieldResponse(
                key=definition.key,
                label=definition.label,
                status="missing",
                value=None,
                source_type="user",
            ),
            VirtualClaimMissingFieldResponse(
                key=definition.key,
                label=definition.label,
                question=definition.question,
            ),
        )

    if field.status == "needs_review":
        return (
            VirtualClaimFieldResponse(
                key=definition.key,
                label=definition.label,
                status="needs_review",
                value=field.value_json,
                source_type=field.source_type,  # type: ignore[arg-type]
            ),
            VirtualClaimMissingFieldResponse(
                key=definition.key,
                label=definition.label,
                question=definition.question,
            ),
        )

    mapped_status = "present" if field.status == "present" else "derived"
    return (
        VirtualClaimFieldResponse(
            key=definition.key,
            label=definition.label,
            status=mapped_status,  # type: ignore[arg-type]
            value=field.value_json,
            source_type=field.source_type,  # type: ignore[arg-type]
        ),
        VirtualClaimMissingFieldResponse(
            key=definition.key,
            label=definition.label,
            question=definition.question,
        ),
    )


def _get_or_create_field(
    db: Session,
    draft: VirtualClaimDraft,
    key: str,
    *,
    allocated_id: int | None = None,
) -> VirtualClaimField:
    for field in draft.fields:
        if field.field_key == key:
            return field
    field = db.execute(
        select(VirtualClaimField).where(
            VirtualClaimField.draft_id == draft.id,
            VirtualClaimField.field_key == key,
        )
    ).scalar_one_or_none()
    if field is not None:
        return field
    field = VirtualClaimField(
        id=allocated_id if allocated_id is not None else next_id(db, VirtualClaimField),
        draft_id=draft.id,
        clinic_id=draft.clinic_id,
        field_key=key,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    draft.fields.append(field)
    return field


def _lock_virtual_claim_draft(db: Session, draft_id: int) -> VirtualClaimDraft:
    return db.execute(
        select(VirtualClaimDraft).where(VirtualClaimDraft.id == draft_id).with_for_update()
    ).scalar_one()


def _list_virtual_claim_fields(
    db: Session,
    draft: VirtualClaimDraft,
    key: str,
) -> list[VirtualClaimField]:
    fields_by_id: dict[int, VirtualClaimField] = {}
    for field in draft.fields:
        if field.field_key == key:
            fields_by_id[field.id] = field
    for field in db.execute(
        select(VirtualClaimField)
        .where(
            VirtualClaimField.draft_id == draft.id,
            VirtualClaimField.field_key == key,
        )
        .order_by(VirtualClaimField.id.asc())
    ).scalars():
        fields_by_id[field.id] = field
    return [fields_by_id[field_id] for field_id in sorted(fields_by_id)]


def _find_virtual_claim_field(
    db: Session,
    draft: VirtualClaimDraft,
    key: str,
) -> VirtualClaimField | None:
    fields = _list_virtual_claim_fields(db, draft, key)
    if not fields:
        return None
    retained = fields[0]
    for duplicate in fields[1:]:
        db.delete(duplicate)
    return retained


def set_virtual_claim_field(
    db: Session,
    draft: VirtualClaimDraft,
    *,
    key: str,
    value: Any,
    status: Literal["missing", "present", "derived", "needs_review"],
    source_type: SourceType,
    source_ref_json: dict[str, Any] | None,
    existing: VirtualClaimField | None = None,
    allocated_id: int | None = None,
) -> VirtualClaimField:
    field = existing or _find_virtual_claim_field(db, draft, key)
    if field is None:
        field = VirtualClaimField(
            id=allocated_id if allocated_id is not None else next_id(db, VirtualClaimField),
            draft_id=draft.id,
            clinic_id=draft.clinic_id,
            field_key=key,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        draft.fields.append(field)
    field.value_json = value
    field.status = status
    field.source_type = source_type
    field.source_ref_json = source_ref_json
    field.updated_at = utcnow()
    db.add(field)
    return field


def _list_virtual_claim_questions(
    db: Session,
    draft: VirtualClaimDraft,
) -> list[VirtualClaimQuestion]:
    questions_by_id: dict[int, VirtualClaimQuestion] = {}
    for question in draft.questions:
        questions_by_id[question.id] = question
    for question in db.execute(
        select(VirtualClaimQuestion)
        .where(VirtualClaimQuestion.draft_id == draft.id)
        .order_by(VirtualClaimQuestion.id.asc())
    ).scalars():
        questions_by_id[question.id] = question
    return [questions_by_id[question_id] for question_id in sorted(questions_by_id)]


def set_virtual_claim_question(
    db: Session,
    draft: VirtualClaimDraft,
    *,
    question_key: str,
    prompt: str,
    status: Literal["open", "answered", "dismissed"],
    answer_json: Any,
    existing: VirtualClaimQuestion | None = None,
    allocated_id: int | None = None,
) -> VirtualClaimQuestion:
    question = existing
    if question is None:
        question = VirtualClaimQuestion(
            id=allocated_id if allocated_id is not None else next_id(db, VirtualClaimQuestion),
            draft_id=draft.id,
            clinic_id=draft.clinic_id,
            question_key=question_key,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        draft.questions.append(question)
    question.prompt = prompt
    question.status = status
    question.answer_json = answer_json
    question.updated_at = utcnow()
    db.add(question)
    return question


def _normalize_field_value(
    definition: ChecklistFieldDefinition,
    value: Any,
) -> tuple[Any, Literal["missing", "present", "derived", "needs_review"]]:
    if definition.value_type == "date":
        if _is_blank(value):
            return None, "missing"
        coerced = _coerce_iso_date(value)
        if coerced is None:
            return str(value), "needs_review"
        return coerced.isoformat(), "present"

    if definition.value_type == "bool":
        if _is_blank(value):
            return None, "missing"
        coerced = _coerce_booleanish(value)
        if coerced is not None:
            return coerced, "present" if coerced else "needs_review"
        if isinstance(value, str):
            rendered = value.strip()
            if rendered:
                return rendered, "present"
        return str(value), "needs_review"

    if definition.value_type == "number":
        if _is_blank(value):
            return None, "missing"
        coerced = _coerce_number(value)
        if coerced is None:
            return str(value), "needs_review"
        return coerced, "present"

    if _is_blank(value):
        return None, "missing"
    rendered = str(value).strip()
    if definition.key == "diagnosis.code":
        rendered = rendered.upper()
    return rendered, "present"


def _coerce_booleanish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"yes", "true", "present", "documented", "ok", "ready", "respected"}:
        return True
    if lowered in {"no", "false", "not documented", "missing", "not respected"}:
        return False
    return None


def _coerce_iso_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _coerce_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = float(stripped)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _coerce_optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _resolve_insurance_company_id(
    db: Session,
    *,
    insurance_company_id: int | str | None,
    insurance_company_name: str | None,
) -> int | None:
    resolved_id = _coerce_optional_int(insurance_company_id)
    if resolved_id is not None:
        company = db.get(InsuranceCompany, resolved_id)
        return company.id if company is not None else None

    fallback_name = insurance_company_name
    if fallback_name is None and isinstance(insurance_company_id, str):
        stripped = insurance_company_id.strip()
        if stripped and not stripped.isdigit():
            fallback_name = stripped
    normalized_name = _coerce_optional_str(fallback_name)
    if normalized_name is None:
        return None

    exact_match = (
        db.execute(
            select(InsuranceCompany)
            .where(InsuranceCompany.name.ilike(normalized_name))
            .order_by(InsuranceCompany.id.asc())
        )
        .scalars()
        .first()
    )
    if exact_match is not None:
        return exact_match.id

    partial_match = (
        db.execute(
            select(InsuranceCompany)
            .where(InsuranceCompany.name.ilike(f"%{normalized_name}%"))
            .order_by(InsuranceCompany.id.asc())
        )
        .scalars()
        .first()
    )
    return partial_match.id if partial_match is not None else None


def _resolve_patient_id_from_query(
    db: Session,
    *,
    clinic_id: int,
    patient_query: str,
) -> int | None:
    stripped = patient_query.strip()
    if not stripped:
        return None
    tokens = [token for token in stripped.split() if token]
    query = f"%{stripped}%"
    filters = [
        Patient.first_name.ilike(query),
        Patient.last_name.ilike(query),
    ]
    if tokens:
        filters.append(Patient.first_name.ilike(f"%{tokens[0]}%"))
    rows = (
        db.execute(
            select(Patient)
            .where(
                Patient.clinic_id == clinic_id,
                or_(*filters),
            )
            .order_by(Patient.id.asc())
        )
        .scalars()
        .all()
    )
    if len(rows) == 1:
        return rows[0].id
    if len(tokens) >= 2:
        exact_matches = [
            patient
            for patient in rows
            if all(
                token.lower() in f"{patient.first_name} {patient.last_name}".lower()
                for token in tokens
            )
        ]
        if len(exact_matches) == 1:
            return exact_matches[0].id
    return None


def _coerce_optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "" or value.strip().lower() in {"unknown", "missing", "none"}
    if isinstance(value, list | dict):
        return len(value) == 0
    return False


def _field_value(draft: VirtualClaimDraft, key: str) -> Any:
    for field in draft.fields:
        if field.field_key == key:
            return field.value_json
    return None


def _patient_name(patient: Patient | None) -> str | None:
    if patient is None:
        return None
    parts = [patient.first_name, patient.last_name]
    rendered = " ".join(part for part in parts if part)
    return rendered or None


def _dedupe_fields(items: list[VirtualClaimFieldResponse]) -> list[VirtualClaimFieldResponse]:
    deduped: dict[str, VirtualClaimFieldResponse] = {}
    for item in items:
        deduped[item.key] = item
    return list(deduped.values())


def _dedupe_missing_fields(
    items: list[VirtualClaimMissingFieldResponse],
) -> list[VirtualClaimMissingFieldResponse]:
    deduped: dict[str, VirtualClaimMissingFieldResponse] = {}
    for item in items:
        deduped[item.key] = item
    return list(deduped.values())
