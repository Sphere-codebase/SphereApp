"""Tool argument schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RequestFormField(BaseModel):
    name: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    required: bool = False


class SearchPatientsArgs(BaseModel):
    query: str = Field(..., min_length=1)


class GetPatientArgs(BaseModel):
    patient_id: int


class GetClaimArgs(BaseModel):
    claim_id: int


class ListClaimsArgs(BaseModel):
    patient_id: int


class RequestFormArgs(BaseModel):
    fields: list[RequestFormField]


class CreateClaimDraftArgs(BaseModel):
    patient_id: int
    fields: dict[str, Any]
    confirm: bool = False


class GetVirtualClaimArgs(BaseModel):
    pass


class GetVirtualClaimChecklistArgs(BaseModel):
    pass


class BootstrapVirtualClaimContextArgs(BaseModel):
    patient_id: int | None = None
    patient_query: str | None = None
    insurance_company_id: int | None = None
    insurance_company_name: str | None = None
    procedure_code: str | None = None


class VirtualClaimFieldUpdate(BaseModel):
    key: str = Field(
        ...,
        description=(
            "Supported keys include insurance.member_id, insurance.group_number, "
            "insurance.policy_number, service_date, service.rendering_provider, "
            "service.quantity, service.modifier, diagnosis.code, diagnosis.description, "
            "clinical.radiculopathy, clinical.functional_limitation, "
            "clinical.conservative_treatment, clinical.imaging_guidance, "
            "clinical.radiology_consistency, clinical.neuro_exam, clinical.mri_or_emg, "
            "treatment.initial_tfesi, utilization.level_limit_ok, "
            "utilization.frequency_limit_ok."
        ),
    )
    value: Any = None


class UpdateVirtualClaimFieldsArgs(BaseModel):
    fields: list[VirtualClaimFieldUpdate] = Field(default_factory=list, min_length=1)
    source_type: str = Field(default="llm_extracted", pattern="^(user|llm_extracted)$")


class UpdateVirtualClaimArgs(BaseModel):
    patient_id: int | None = None
    insurance_company_id: int | None = None
    procedure_code: str | None = None
    fields: list[VirtualClaimFieldUpdate] = Field(default_factory=list)
    source_type: str = Field(default="llm_extracted", pattern="^(user|llm_extracted)$")


class EvaluateClaimReadinessArgs(BaseModel):
    pass


class ListMissingClaimFieldsArgs(BaseModel):
    pass


class ListMissingVirtualClaimFieldsArgs(BaseModel):
    pass


class ExplainVirtualClaimPolicyArgs(BaseModel):
    pass


class ProposeMaterializeVirtualClaimArgs(BaseModel):
    confirm: bool = False


class UpdateClaimFieldsArgs(BaseModel):
    claim_id: int
    patch: dict[str, Any]
    confirm: bool = False


class GetAccountArgs(BaseModel):
    pass


class TimeNowArgs(BaseModel):
    tz: str = "Asia/Tbilisi"


class ParsePolicyLinkAndStoreArgs(BaseModel):
    policy_link_id: int
    confirm: bool = False


class ListProcedureCodesArgs(BaseModel):
    query: str | None = None
    limit: int = Field(default=50, ge=1, le=200)


class GetProcedureCodeArgs(BaseModel):
    code: str


class ListPolicyLinksForCodeArgs(BaseModel):
    code: str
    insurance_company_id: int | None = None


class GetPolicyRulesForLinkArgs(BaseModel):
    policy_link_id: int = Field(..., ge=1)


class ExplainCoverageForCodeArgs(BaseModel):
    code: str
    claim_id: int | None = None
    max_examples: int = Field(default=5, ge=1, le=10)


class GetBotCapabilitiesArgs(BaseModel):
    include_schemas: bool = False
    category: str = "all"
    language: str = "ru"


class BotCapabilityItem(BaseModel):
    tool: str
    summary: str
    examples: list[str]
    limits: list[str]
    input_schema: dict[str, Any] | None = None


class BotCapabilityCategory(BaseModel):
    id: str
    title: str
    capabilities: list[BotCapabilityItem]


class BotCapabilitiesResponse(BaseModel):
    name: str
    version: str
    generated_at: str
    categories: list[BotCapabilityCategory]
    global_limits: list[str]
