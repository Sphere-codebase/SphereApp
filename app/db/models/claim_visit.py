"""Claim-visit association table."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.models.base import Base

claim_visits = Table(
    "claim_visits",
    Base.metadata,
    Column("claim_id", UUID(as_uuid=True), ForeignKey("claims.id"), primary_key=True),
    Column("visit_id", UUID(as_uuid=True), ForeignKey("visits.id"), primary_key=True),
    UniqueConstraint("claim_id", "visit_id", name="uq_claim_visits_claim_id_visit_id"),
)
