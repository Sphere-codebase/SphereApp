"""Tool argument schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchPatientsArgs(BaseModel):
    query: str = Field(..., min_length=1)


class GetPatientArgs(BaseModel):
    patient_id: int


class GetClaimArgs(BaseModel):
    claim_id: int


class ListClaimsArgs(BaseModel):
    patient_id: int


class RequestFormArgs(BaseModel):
    fields: list[dict[str, Any]]


class CreateClaimDraftArgs(BaseModel):
    patient_id: int
    fields: dict[str, Any]
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
