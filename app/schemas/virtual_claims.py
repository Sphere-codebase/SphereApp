"""Virtual claim checklist schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ChecklistStatus = Literal["missing", "present", "derived", "needs_review"]
ChecklistSource = Literal["database", "user", "llm_extracted", "derived", "policy"]


class VirtualClaimFieldInput(BaseModel):
    key: str = Field(..., min_length=1)
    value: Any = None


class VirtualClaimBootstrapRequest(BaseModel):
    patient_id: int | None = None
    insurance_company_id: int | None = None
    procedure_code: str | None = None


class VirtualClaimPatchRequest(BaseModel):
    patient_id: int | None = None
    insurance_company_id: int | None = None
    procedure_code: str | None = None
    fields: list[VirtualClaimFieldInput] = Field(default_factory=list)
    source_type: Literal["user", "llm_extracted"] = "user"


class VirtualClaimFieldResponse(BaseModel):
    key: str
    label: str
    status: ChecklistStatus
    value: Any = None
    source_type: ChecklistSource


class VirtualClaimMissingFieldResponse(BaseModel):
    key: str
    label: str
    question: str


class VirtualClaimQuestionResponse(BaseModel):
    question_key: str
    prompt: str
    status: Literal["open", "answered", "dismissed"]
    answer: Any = None


class VirtualClaimPartySummary(BaseModel):
    id: int | None = None
    name: str | None = None
    date_of_birth: str | None = None


class VirtualClaimProcedureSummary(BaseModel):
    code: str | None = None
    description: str | None = None


class VirtualClaimPolicySummaryResponse(BaseModel):
    policy_link_id: int | None = None
    policy_rule_id: int | None = None
    policy_url: str | None = None
    title: str | None = None
    extracted_at: datetime | None = None
    rules_json: Any = None
    criteria_json: Any = None
    notes_json: Any = None


class VirtualClaimChecklistValue(BaseModel):
    value: Any = None
    status: ChecklistStatus
    source_type: ChecklistSource
    required: bool = True
    label: str | None = None


class VirtualClaimPatientChecklist(BaseModel):
    patient_id: VirtualClaimChecklistValue
    first_name: VirtualClaimChecklistValue
    last_name: VirtualClaimChecklistValue
    date_of_birth: VirtualClaimChecklistValue


class VirtualClaimPayerChecklist(BaseModel):
    insurance_company_id: VirtualClaimChecklistValue
    payer_name: VirtualClaimChecklistValue
    member_id: VirtualClaimChecklistValue
    group_number: VirtualClaimChecklistValue
    policy_number: VirtualClaimChecklistValue


class VirtualClaimServiceChecklist(BaseModel):
    procedure_code: VirtualClaimChecklistValue
    procedure_description: VirtualClaimChecklistValue
    service_date: VirtualClaimChecklistValue
    rendering_provider: VirtualClaimChecklistValue
    quantity: VirtualClaimChecklistValue
    modifier: VirtualClaimChecklistValue


class VirtualClaimDiagnosisChecklist(BaseModel):
    diagnosis_code: VirtualClaimChecklistValue
    diagnosis_description: VirtualClaimChecklistValue


class VirtualClaimPolicyChecklist(BaseModel):
    policy_link_id: VirtualClaimChecklistValue
    policy_url: VirtualClaimChecklistValue
    stored_rules_available: VirtualClaimChecklistValue
    radiculopathy_evidence: VirtualClaimChecklistValue
    dermatomal_distribution: VirtualClaimChecklistValue
    functional_limitation: VirtualClaimChecklistValue
    conservative_treatment_failed: VirtualClaimChecklistValue
    imaging_guidance: VirtualClaimChecklistValue
    MRI_or_CT_or_EMG_evidence: VirtualClaimChecklistValue
    neuro_exam_evidence: VirtualClaimChecklistValue
    frequency_session_limits_respected: VirtualClaimChecklistValue
    radiologic_findings_consistent: VirtualClaimChecklistValue | None = None
    initial_therapeutic_tfesi: VirtualClaimChecklistValue | None = None
    vertebral_level_limits_respected: VirtualClaimChecklistValue | None = None


class VirtualClaimReadinessChecklist(BaseModel):
    ready_to_draft: bool
    missing_fields: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    next_questions: list[str] = Field(default_factory=list)


class VirtualClaimChecklistResponse(BaseModel):
    patient: VirtualClaimPatientChecklist
    payer_insurance: VirtualClaimPayerChecklist
    service: VirtualClaimServiceChecklist
    diagnosis: VirtualClaimDiagnosisChecklist
    policy_medical_necessity: VirtualClaimPolicyChecklist
    readiness: VirtualClaimReadinessChecklist


class VirtualClaimResponse(BaseModel):
    draft_id: int
    session_id: int
    status: Literal["open", "ready", "materialized", "archived"]
    readiness: bool
    readiness_reason: str | None = None
    patient: VirtualClaimPartySummary | None = None
    payer: VirtualClaimPartySummary | None = None
    procedure: VirtualClaimProcedureSummary | None = None
    materialized_claim_id: int | None = None
    policy_summary: VirtualClaimPolicySummaryResponse | None = None
    checklist: VirtualClaimChecklistResponse
    filled: list[VirtualClaimFieldResponse] = Field(default_factory=list)
    missing: list[VirtualClaimFieldResponse] = Field(default_factory=list)
    needs_review: list[VirtualClaimFieldResponse] = Field(default_factory=list)
    policy_constraints: list[VirtualClaimFieldResponse] = Field(default_factory=list)
    missing_fields: list[VirtualClaimMissingFieldResponse] = Field(default_factory=list)
    follow_up_questions: list[VirtualClaimQuestionResponse] = Field(default_factory=list)
    updated_at: datetime | None = None


class VirtualClaimMaterializeRequest(BaseModel):
    confirm: bool = False


class VirtualClaimMaterializeResponse(BaseModel):
    action_required: bool = False
    proposal: dict[str, Any] | None = None
    claim_id: int | None = None
    draft: VirtualClaimResponse
