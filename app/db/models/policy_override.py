"""Policy overrides for clinic and doctor."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class ClinicPolicyOverride(TimestampMixin, Base):
    __tablename__ = "clinic_policy_overrides"
    __table_args__ = (
        Index("ix_clinic_policy_overrides_clinic_id", "clinic_id"),
        Index("ix_clinic_policy_overrides_policy_link_id", "policy_link_id"),
        Index(
            "uq_clinic_policy_overrides_clinic_id_policy_link_id",
            "clinic_id",
            "policy_link_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    clinic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clinics.id"), nullable=False, server_default=text("1")
    )
    policy_link_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policy_links.id"), nullable=False
    )
    override_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    policy_link = relationship("PolicyLink", backref="clinic_overrides")


class DoctorPolicyOverride(TimestampMixin, Base):
    __tablename__ = "doctor_policy_overrides"
    __table_args__ = (
        Index("ix_doctor_policy_overrides_doctor_id", "doctor_id"),
        Index("ix_doctor_policy_overrides_clinic_id", "clinic_id"),
        Index("ix_doctor_policy_overrides_policy_link_id", "policy_link_id"),
        Index(
            "uq_doctor_policy_overrides_doctor_id_policy_link_id",
            "doctor_id",
            "policy_link_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    doctor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    clinic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clinics.id"), nullable=False, server_default=text("1")
    )
    policy_link_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policy_links.id"), nullable=False
    )
    override_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    policy_link = relationship("PolicyLink", backref="doctor_overrides")
