"""Shared exception types."""

from __future__ import annotations


class ClinicBlockedError(Exception):
    """Raised when a user belongs to a blocked clinic and access is denied."""

    def __init__(self, clinic_id: int) -> None:
        self.clinic_id = clinic_id
        super().__init__("Clinic is blocked")
