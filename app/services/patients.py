"""Patient creation and lookup services."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories.patients import InsuranceCompanyRepository, PatientRepository
from app.schemas.patients import (
    InsuranceCardResponse,
    InsuranceCompanyListItem,
    InsuranceCompanyListResponse,
    NewPatientCreateRequest,
    NewPatientCreateResponse,
    PatientAddressResponse,
    PatientInsuranceResponse,
    PatientPhoneInput,
)


@dataclass(frozen=True)
class InsuranceCompanyListFilters:
    q: str | None = None
    limit: int = 20
    offset: int = 0


class PatientService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_new_patient(
        self,
        *,
        current_user: User,
        payload: NewPatientCreateRequest,
    ) -> NewPatientCreateResponse:
        insurances = payload.insurances or []
        if len(insurances) > 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At most two insurance policies are allowed",
            )

        priorities = [item.priority for item in insurances]
        if len(set(priorities)) != len(priorities):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Insurance priorities must be unique",
            )

        company_ids = [item.insurance_company_id for item in insurances]
        if company_ids:
            existing_company_ids = InsuranceCompanyRepository.ensure_ids_exist(
                self._db,
                company_ids=company_ids,
            )
            missing = [
                company_id for company_id in company_ids if company_id not in existing_company_ids
            ]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Insurance company not found: {missing[0]}",
                )

        chart_number = payload.chart_number.strip() if payload.chart_number else None
        if chart_number and PatientRepository.chart_number_exists(
            self._db,
            clinic_id=current_user.clinic_id,
            chart_number=chart_number,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chart number already exists in clinic",
            )

        first_name, last_name = self._split_name(payload.patient_name)

        transaction = self._db.begin_nested() if self._db.in_transaction() else self._db.begin()
        try:
            with transaction:
                address = None
                if payload.address is not None:
                    address = PatientRepository.create_address(
                        self._db,
                        line1=payload.address.line1,
                        line2=payload.address.line2,
                        city=payload.address.city,
                        state=payload.address.state,
                        zip_code=payload.address.zip,
                        country=payload.address.country,
                    )

                patient = PatientRepository.create_patient(
                    self._db,
                    doctor_id=current_user.id,
                    clinic_id=current_user.clinic_id,
                    first_name=first_name,
                    last_name=last_name,
                    chart_number=chart_number,
                    provider_name=payload.provider_name,
                    gender=payload.gender,
                    primary_phone=payload.phones.primary,
                    secondary_phone=payload.phones.secondary,
                    address_id=address.id if address else None,
                )

                insurance_items: list[PatientInsuranceResponse] = []
                for insurance in insurances:
                    policy = PatientRepository.create_patient_insurance_policy(
                        self._db,
                        clinic_id=current_user.clinic_id,
                        patient_id=patient.id,
                        insurance_company_id=insurance.insurance_company_id,
                        priority=insurance.priority,
                        member_id=insurance.member_id,
                        policy_type=insurance.policy_type,
                        copay_amount=insurance.copay_amount,
                        deductible_amount=insurance.deductible_amount,
                        currency=insurance.currency,
                    )

                    cards: list[InsuranceCardResponse] = []
                    if insurance.card is not None:
                        card = PatientRepository.create_insurance_card(
                            self._db,
                            policy_id=policy.id,
                            side=insurance.card.side,
                            storage_key=insurance.card.storage_key,
                            content_type=insurance.card.content_type,
                            size_bytes=insurance.card.size_bytes,
                        )
                        cards.append(
                            InsuranceCardResponse(
                                side=card.side,
                                storage_key=card.storage_key,
                                content_type=card.content_type,
                                size_bytes=card.size_bytes,
                                uploaded_at=card.uploaded_at,
                            )
                        )

                    insurance_items.append(
                        PatientInsuranceResponse(
                            priority=policy.priority,
                            insurance_company_id=policy.insurance_company_id,
                            member_id=policy.member_id,
                            policy_type=policy.policy_type,
                            copay_amount=float(policy.copay_amount)
                            if policy.copay_amount is not None
                            else None,
                            deductible_amount=float(policy.deductible_amount)
                            if policy.deductible_amount is not None
                            else None,
                            currency=policy.currency,
                            cards=cards,
                        )
                    )
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient creation conflict",
            ) from exc

        return NewPatientCreateResponse(
            id=patient.id,
            clinic_id=patient.clinic_id,
            first_name=patient.first_name,
            last_name=patient.last_name,
            chart_number=patient.chart_number,
            provider_name=patient.provider_name,
            gender=patient.gender,
            phones=PatientPhoneInput(
                primary=patient.primary_phone,
                secondary=patient.secondary_phone,
            ),
            address=PatientAddressResponse(
                line1=address.line1,
                line2=address.line2,
                city=address.city,
                state=address.state,
                zip=address.zip,
                country=address.country,
            )
            if address is not None
            else None,
            insurances=insurance_items,
            created_at=patient.created_at,
        )

    def list_insurance_companies(
        self,
        *,
        filters: InsuranceCompanyListFilters,
    ) -> InsuranceCompanyListResponse:
        items, total = InsuranceCompanyRepository.list_for_dropdown(
            self._db,
            q=filters.q,
            limit=filters.limit,
            offset=filters.offset,
        )
        return InsuranceCompanyListResponse(
            items=[InsuranceCompanyListItem(id=item.id, name=item.name) for item in items],
            limit=filters.limit,
            offset=filters.offset,
            total=total,
        )

    @staticmethod
    def _split_name(full_name: str) -> tuple[str | None, str | None]:
        parts = [part for part in full_name.strip().split(" ") if part]
        if not parts:
            return None, None
        if len(parts) == 1:
            return parts[0], None
        return parts[0], " ".join(parts[1:])
