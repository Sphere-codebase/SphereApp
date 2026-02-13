"""Claim summary service for My Claims page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories.claims import ClaimsRepository
from app.schemas.claims import MyClaimItemSchema, MyClaimsListResponseSchema


@dataclass(frozen=True)
class MyClaimsFilters:
    limit: int = 20
    offset: int = 0
    q: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class ClaimsService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_my_claims_summary(
        self,
        current_user: User,
        filters: MyClaimsFilters,
    ) -> MyClaimsListResponseSchema:
        if filters.limit < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="limit must be >= 1",
            )
        if filters.offset < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="offset must be >= 0",
            )
        if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="date_from must be <= date_to",
            )

        rows, total = ClaimsRepository.list_my_claims_summary(
            self._db,
            doctor_id=current_user.id,
            limit=filters.limit,
            offset=filters.offset,
            q=filters.q,
            date_from=filters.date_from,
            date_to=filters.date_to,
        )

        items: list[MyClaimItemSchema] = []
        for claim, patient, company, requested_total, approved_total in rows:
            patient_name = " ".join(
                part for part in [patient.first_name or "", patient.last_name or ""] if part
            ).strip()
            items.append(
                MyClaimItemSchema(
                    id=claim.id,
                    patient_name=patient_name,
                    date_of_service=claim.service_date,
                    claim_number=claim.claim_number,
                    # No policy identifier is stored; use insurer name as the closest display value.
                    policy=company.name if company else None,
                    # paid_amount represents the requested amount, stored as billed_amount.
                    paid_amount=float(requested_total or 0),
                    # billed_amount represents the approved amount, stored as allowed_amount.
                    billed_amount=float(approved_total or 0),
                    # Currency isn't modeled; default to USD.
                    currency="USD",
                )
            )

        return MyClaimsListResponseSchema(
            items=items,
            limit=filters.limit,
            offset=filters.offset,
            total=total,
        )
