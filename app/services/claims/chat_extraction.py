"""Deterministic virtual-claim fact extraction from chat text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.claims.normalization import normalize_procedure_code

SERVICE_DATE_PATTERNS = (
    re.compile(
        r"\b(?:planned\s+)?service\s+date(?:\s+is|:)?\s*(\d{4}-\d{2}-\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdate\s+of\s+service(?:\s+is|:)?\s*(\d{4}-\d{2}-\d{2})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdos(?:\s+is|:)?\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
)
DIAGNOSIS_CODE_PATTERN = re.compile(r"\b([A-Z]\d{1,2}(?:\.\d{1,4})?)\b", re.IGNORECASE)
PATIENT_NAME_PATTERN = re.compile(
    r"\bpatient\s+([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){1,4})(?=\s+for\b|[.,]|$)",
    re.IGNORECASE,
)
PAYER_PATTERNS = {
    "Aetna": re.compile(r"\baetna\b", re.IGNORECASE),
}
CLAIM_PREP_KEYWORDS = (
    "claim",
    "prepare",
    "draft",
    "payer",
    "patient",
    "diagnosis",
    "service date",
    "cpt",
    "procedure code",
    "radiculopathy",
    "fluoroscopy",
    "mri",
    "neuro exam",
)


@dataclass(frozen=True)
class ExtractedVirtualClaimPatch:
    patient_query: str | None = None
    insurance_company_name: str | None = None
    procedure_code: str | None = None
    fields: list[tuple[str, Any]] = field(default_factory=list)

    @property
    def has_updates(self) -> bool:
        return any(
            [
                self.patient_query is not None,
                self.insurance_company_name is not None,
                self.procedure_code is not None,
                bool(self.fields),
            ]
        )


def looks_like_claim_prep_message(message: str, *, has_virtual_claim: bool = False) -> bool:
    lowered = message.lower()
    return has_virtual_claim or any(keyword in lowered for keyword in CLAIM_PREP_KEYWORDS)


def extract_virtual_claim_patch(message: str) -> ExtractedVirtualClaimPatch:
    updates: dict[str, Any] = {}
    sentences = _split_sentences(message)
    lowered = message.lower()

    patient_query = _extract_patient_query(message)
    payer_name = _extract_payer_name(message)
    procedure_code = normalize_procedure_code(message)

    service_date = _extract_service_date(message)
    if service_date is not None:
        updates["service_date"] = service_date

    diagnosis_code = _extract_diagnosis_code(message)
    if diagnosis_code is not None:
        updates["diagnosis.code"] = diagnosis_code
    diagnosis_description = _extract_diagnosis_description(message, diagnosis_code)
    if diagnosis_description is not None:
        updates["diagnosis.description"] = diagnosis_description

    radiculopathy_sentence = _find_sentence(
        sentences,
        "radiculopathy",
        "radicular pain",
        "radicular symptoms",
    )
    if radiculopathy_sentence is not None:
        updates["clinical.radiculopathy"] = radiculopathy_sentence
    dermatomal_sentence = _find_sentence(sentences, "dermatomal")
    if dermatomal_sentence is not None:
        updates["clinical.dermatomal_distribution"] = dermatomal_sentence
    elif radiculopathy_sentence is not None and "dermatomal" in radiculopathy_sentence.lower():
        updates["clinical.dermatomal_distribution"] = radiculopathy_sentence

    functional_sentence = _find_sentence(sentences, "functional limitation")
    if functional_sentence is not None:
        updates["clinical.functional_limitation"] = functional_sentence

    conservative_sentence = _find_sentence(
        sentences,
        "physical therapy",
        "pt ",
        "pt.",
        "non-narcotic analgesics",
        "conservative treatment",
    )
    if conservative_sentence is not None and any(
        token in conservative_sentence.lower()
        for token in ("failed", "failure", "did not help", "not improved")
    ):
        updates["clinical.conservative_treatment"] = conservative_sentence

    guidance_sentence = _find_sentence(sentences, "fluoroscopy", "ct guidance")
    if guidance_sentence is not None:
        updates["clinical.imaging_guidance"] = guidance_sentence

    imaging_sentence = _find_sentence(
        sentences,
        "nerve root compression",
        "mri",
        "emg",
        "computed tomography",
    )
    if imaging_sentence is not None and any(
        token in imaging_sentence.lower() for token in ("mri", "ct", "emg", "ncv")
    ):
        updates["clinical.mri_or_emg"] = imaging_sentence

    radiology_sentence = _find_sentence(
        sentences,
        "consistent with symptoms",
        "nerve root compression",
    )
    if radiology_sentence is not None:
        updates["clinical.radiology_consistency"] = radiology_sentence

    neuro_sentence = _find_sentence(
        sentences,
        "neuro exam",
        "altered sensation",
        "diminished reflex",
        "sensory loss",
        "reflex changes",
    )
    if neuro_sentence is not None:
        updates["clinical.neuro_exam"] = neuro_sentence

    tfesi_sentence = _find_sentence(
        sentences,
        "initial therapeutic tfesi",
        "initial tfesi",
    )
    if tfesi_sentence is not None:
        updates["treatment.initial_tfesi"] = tfesi_sentence

    quantity_match = re.search(
        r"\bquantity\s*(?:is|=)?\s*(\d+(?:\.\d+)?)\b",
        message,
        re.IGNORECASE,
    )
    if quantity_match is not None:
        parsed_quantity = quantity_match.group(1)
        updates["service.quantity"] = (
            int(parsed_quantity) if "." not in parsed_quantity else float(parsed_quantity)
        )

    level_sentence = _find_sentence(sentences, "one level", "1 level", "single level")
    if level_sentence is not None:
        updates["utilization.level_limit_ok"] = level_sentence

    frequency_sentence = _find_sentence(
        sentences,
        "session/frequency limits",
        "session limits",
        "frequency limits",
    )
    if frequency_sentence is not None and "respect" in frequency_sentence.lower():
        updates["utilization.frequency_limit_ok"] = frequency_sentence

    if "lumbar radiculopathy" in lowered and "diagnosis.description" not in updates:
        updates["diagnosis.description"] = "Lumbar radiculopathy"

    return ExtractedVirtualClaimPatch(
        patient_query=patient_query,
        insurance_company_name=payer_name,
        procedure_code=procedure_code,
        fields=list(updates.items()),
    )


def _extract_patient_query(message: str) -> str | None:
    match = PATIENT_NAME_PATTERN.search(message)
    if match is None:
        return None
    candidate = " ".join(match.group(1).strip().split())
    return candidate or None


def _extract_payer_name(message: str) -> str | None:
    for payer_name, pattern in PAYER_PATTERNS.items():
        if pattern.search(message):
            return payer_name
    return None


def _extract_service_date(message: str) -> str | None:
    for pattern in SERVICE_DATE_PATTERNS:
        match = pattern.search(message)
        if match is None:
            continue
        candidate = match.group(1)
        try:
            date.fromisoformat(candidate)
        except ValueError:
            continue
        return candidate
    return None


def _extract_diagnosis_code(message: str) -> str | None:
    match = DIAGNOSIS_CODE_PATTERN.search(message)
    if match is None:
        return None
    candidate = match.group(1).upper()
    return candidate if candidate.startswith("M") else None


def _extract_diagnosis_description(message: str, diagnosis_code: str | None) -> str | None:
    if diagnosis_code is None:
        return "Lumbar radiculopathy" if "lumbar radiculopathy" in message.lower() else None
    sentence = _find_sentence(_split_sentences(message), "diagnosis", diagnosis_code.lower())
    if sentence is None:
        return "Lumbar radiculopathy" if "lumbar radiculopathy" in message.lower() else None
    description = re.sub(
        r"^\s*the diagnosis is\s+",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    description = re.sub(
        rf"\b{re.escape(diagnosis_code)}\b",
        "",
        description,
        flags=re.IGNORECASE,
    ).strip(" .:-")
    return description[:1].upper() + description[1:] if description else None


def _split_sentences(message: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|\n+", message)
        if part.strip()
    ]


def _find_sentence(sentences: list[str], *keywords: str) -> str | None:
    lowered_keywords = tuple(keyword.lower() for keyword in keywords if keyword)
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            return sentence.strip()
    return None
