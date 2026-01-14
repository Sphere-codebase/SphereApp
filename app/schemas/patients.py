"""Patient and visit schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PatientCreateRequest(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    date_of_birth: date | None = None
    sex: str | None = None


class PatientUpdateRequest(BaseModel):
    first_name: str | None = Field(None, min_length=1)
    last_name: str | None = Field(None, min_length=1)
    date_of_birth: date | None = None
    sex: str | None = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    first_name: str | None
    last_name: str | None
    date_of_birth: date | None
    sex: str | None
    created_at: datetime
    updated_at: datetime


class VisitCreateRequest(BaseModel):
    visited_at: datetime
    provider: str | None = None
    notes: str | None = None


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    visited_at: datetime
    provider: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
