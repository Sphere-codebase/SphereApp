from app.services.claims.chat_extraction import (
    extract_virtual_claim_patch,
    looks_like_claim_prep_message,
)


def test_extract_virtual_claim_patch_for_initial_bootstrap_message() -> None:
    patch = extract_virtual_claim_patch(
        "I want to prepare a new Aetna claim for patient DAVID R WIENTZEN "
        "for CPT 62323. Planned service date is 2025-05-27."
    )

    assert looks_like_claim_prep_message(
        "I want to prepare a new Aetna claim for patient DAVID R WIENTZEN for CPT 62323."
    )
    assert patch.patient_query == "DAVID R WIENTZEN"
    assert patch.insurance_company_name == "Aetna"
    assert patch.procedure_code == "62323"
    assert ("service_date", "2025-05-27") in patch.fields


def test_extract_virtual_claim_patch_for_clinical_facts_message() -> None:
    patch = extract_virtual_claim_patch(
        "The diagnosis is M54.16 lumbar radiculopathy. "
        "The patient has dermatomal lumbar radicular pain with significant functional limitation. "
        "Physical therapy and non-narcotic analgesics failed. "
        "Fluoroscopy guidance will be used. "
        "MRI within 12 months shows nerve root compression consistent with symptoms. "
        "Neuro exam within 3 months shows altered sensation and diminished reflexes. "
        "This is the initial therapeutic TFESI, quantity 1, one level, and "
        "session/frequency limits are respected."
    )

    extracted = dict(patch.fields)
    assert extracted["diagnosis.code"] == "M54.16"
    assert extracted["diagnosis.description"] == "Lumbar radiculopathy"
    assert "dermatomal" in extracted["clinical.dermatomal_distribution"].lower()
    assert "physical therapy" in extracted["clinical.conservative_treatment"].lower()
    assert "fluoroscopy" in extracted["clinical.imaging_guidance"].lower()
    assert "nerve root compression" in extracted["clinical.mri_or_emg"].lower()
    assert "altered sensation" in extracted["clinical.neuro_exam"].lower()
    assert extracted["service.quantity"] == 1
    assert "one level" in extracted["utilization.level_limit_ok"].lower()
    assert "respected" in extracted["utilization.frequency_limit_ok"].lower()
