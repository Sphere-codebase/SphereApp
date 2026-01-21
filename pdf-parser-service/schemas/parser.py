from __future__ import annotations

from pydantic import BaseModel


class PatientInfo(BaseModel):
    account_number: str | None = None
    name: str | None = None
    date_of_birth: str | None = None


class CodeInfo(BaseModel):
    type: str
    code: str
    description: str | None = None


class AdjustmentInfo(BaseModel):
    amount: str
    type: str
    code: str
    description: str | None = None


class ClaimLineInfo(BaseModel):
    date: str
    cpt: str
    dx: list[str]
    reason_codes: list[str]
    billed_amount: str
    allowed_amount: str
    paid_amount: str
    ratio: float
    adjustments: list[AdjustmentInfo]


class PdfParseResult(BaseModel):
    user_info: PatientInfo
    codes: list[CodeInfo]
    info: list[ClaimLineInfo]


class ParseRequest(BaseModel):
    pdf_url: str | None = None
    pdf_base64: str | None = None
    request_id: str | None = None


class ParseResponse(BaseModel):
    parse_result: PdfParseResult
    request_id: str | None = None
