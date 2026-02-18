"""User model."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin
from app.db.models.enums import UserRole


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_clinic_id", "clinic_id"),
        CheckConstraint(
            "role IN ('doctor', 'chief_doctor', 'clinic_admin', 'platform_staff_admin')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    role: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=UserRole.DOCTOR.value,
        server_default=text("'doctor'"),
    )
    clinic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clinics.id"),
        nullable=False,
        server_default=text("1"),
    )

    roles = relationship("Role", secondary="user_roles", back_populates="users", lazy="selectin")
    clinic = relationship("Clinic", back_populates="users")
