"""Agent tool schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.claims import ClaimDetailResponse, DiagnosisCodeSummary, McpCodeSummary


class AgentPolicyLinkItem(BaseModel):
    mcp_code: str
    policy_link_id: int
    policy_url: str | None


class AgentPolicyLinksResponse(BaseModel):
    items: list[AgentPolicyLinkItem] = Field(default_factory=list)


class AgentPolicyRuleResponse(BaseModel):
    policy_link_id: int
    extracted_at: datetime | None = None
    rules_json: Any | None = None


class AgentClaimContextResponse(BaseModel):
    claim: ClaimDetailResponse
    procedures: list[McpCodeSummary] = Field(default_factory=list)
    diagnoses: list[DiagnosisCodeSummary] = Field(default_factory=list)
    policy_links: list[AgentPolicyLinkItem] = Field(default_factory=list)
    policy_rules: list[AgentPolicyRuleResponse] = Field(default_factory=list)


class AgentClaimUpdateRequest(BaseModel):
    set: dict[str, Any] | None = None
    patient_set: dict[str, Any] | None = None


class AgentCodeUpdateRequest(BaseModel):
    code: str


class ClaimRequirementField(BaseModel):
    key: str
    source: Literal["base", "policy"]
    severity: Literal["required", "recommended"]
    reason: str | None = None


class ClaimMissingField(BaseModel):
    key: str
    question: str


class ClaimRequirementsResponse(BaseModel):
    claim_id: int
    required_fields: list[ClaimRequirementField] = Field(default_factory=list)
    missing: list[ClaimMissingField] = Field(default_factory=list)
    is_complete: bool


class ClaimValidationResponse(BaseModel):
    is_complete: bool
    missing: list[ClaimMissingField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
