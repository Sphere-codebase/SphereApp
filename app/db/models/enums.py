"""Shared enum values for domain models."""

from __future__ import annotations

from enum import Enum


class ClaimStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PAID = "PAID"
    DENIED = "DENIED"
