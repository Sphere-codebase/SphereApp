"""Shared enum values for domain models."""

from __future__ import annotations

from enum import Enum


class ClaimStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PAID = "PAID"
    DENIED = "DENIED"


class UserRole(str, Enum):
    DOCTOR = "doctor"
    CHIEF_DOCTOR = "chief_doctor"
    CLINIC_ADMIN = "clinic_admin"
    PLATFORM_STAFF_ADMIN = "platform_staff_admin"
