"""Admin catalog schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import AnyUrl, BaseModel, ConfigDict, Field


class InsuranceCompanyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    stedi_trading_partner_service_id: str | None = None


class InsuranceCompanyUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1)
    stedi_trading_partner_service_id: str | None = None


class InsuranceCompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    stedi_trading_partner_service_id: str | None
    created_at: datetime | None


class McpCodeCreateRequest(BaseModel):
    code: str = Field(..., min_length=1)
    description: str | None = None


class McpCodeUpdateRequest(BaseModel):
    description: str | None = None


class McpCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str | None


class PolicyLinkCreateRequest(BaseModel):
    insurance_company_id: int
    mcp_code: str = Field(..., min_length=1)
    policy_url: AnyUrl


class PolicyLinkUpdateRequest(BaseModel):
    insurance_company_id: int | None = None
    mcp_code: str | None = None
    policy_url: AnyUrl | None = None


class PolicyLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    insurance_company_id: int
    mcp_code: str
    policy_url: AnyUrl
    created_at: datetime | None


class PolicyRulesParseRequest(BaseModel):
    confirm: bool = False


class PolicyRuleResponse(BaseModel):
    policy_rules_id: int
    policy_link_id: int
    extracted_at: datetime
    title: str | None
    next_review_iso: date | None
    criteria_json: Any | None
    notes_json: Any | None
    medical_necessity_clean: str | None


class DiagnosisCodeCreateRequest(BaseModel):
    code: str = Field(..., min_length=1)
    description: str | None = None


class DiagnosisCodeUpdateRequest(BaseModel):
    description: str | None = None


class DiagnosisCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str | None
