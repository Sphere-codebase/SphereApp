import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import VirtualClaimPanel from "@/components/workspace/VirtualClaimPanel";
import type { VirtualClaimDTO } from "@/types/virtualClaim";

const draft: VirtualClaimDTO = {
  draft_id: 101,
  session_id: 55,
  status: "open",
  readiness: false,
  readiness_reason: "Checklist is missing required fields.",
  patient: { id: 7, name: "DAVID R WIENTZEN", date_of_birth: "1966-08-31" },
  payer: { id: 12, name: "Aetna" },
  procedure: {
    code: "62323",
    description: "Injection(s), of diagnostic or therapeutic substance(s)",
  },
  materialized_claim_id: null,
  policy_summary: {
    policy_link_id: 88,
    policy_rule_id: 99,
    policy_url: "https://example.com/aetna-62323",
    title: "Aetna 62323 Medical Necessity",
    extracted_at: "2026-04-24T00:00:00",
  },
  checklist: {
    patient: {
      patient_id: {
        value: 7,
        status: "present",
        source_type: "database",
        required: true,
        label: "Patient ID",
      },
      first_name: {
        value: "DAVID",
        status: "present",
        source_type: "database",
        required: true,
        label: "First name",
      },
      last_name: {
        value: "WIENTZEN",
        status: "present",
        source_type: "database",
        required: true,
        label: "Last name",
      },
      date_of_birth: {
        value: "1966-08-31",
        status: "present",
        source_type: "database",
        required: true,
        label: "Date of birth",
      },
    },
    payer_insurance: {
      insurance_company_id: {
        value: 12,
        status: "present",
        source_type: "database",
        required: true,
        label: "Insurance company ID",
      },
      payer_name: {
        value: "Aetna",
        status: "present",
        source_type: "database",
        required: true,
        label: "Payer name",
      },
      member_id: {
        value: null,
        status: "missing",
        source_type: "user",
        required: true,
        label: "Member ID",
      },
      group_number: {
        value: null,
        status: "missing",
        source_type: "user",
        required: false,
        label: "Group number",
      },
      policy_number: {
        value: null,
        status: "missing",
        source_type: "user",
        required: false,
        label: "Policy number",
      },
    },
    service: {
      procedure_code: {
        value: "62323",
        status: "present",
        source_type: "database",
        required: true,
        label: "Procedure code",
      },
      procedure_description: {
        value: "Injection(s), of diagnostic or therapeutic substance(s)",
        status: "present",
        source_type: "database",
        required: true,
        label: "Procedure description",
      },
      service_date: {
        value: null,
        status: "missing",
        source_type: "user",
        required: true,
        label: "Service date",
      },
      rendering_provider: {
        value: null,
        status: "missing",
        source_type: "user",
        required: true,
        label: "Rendering provider",
      },
      quantity: {
        value: 1,
        status: "derived",
        source_type: "derived",
        required: false,
        label: "Quantity",
      },
      modifier: {
        value: null,
        status: "missing",
        source_type: "user",
        required: false,
        label: "Modifier",
      },
    },
    diagnosis: {
      diagnosis_code: {
        value: null,
        status: "missing",
        source_type: "user",
        required: true,
        label: "Diagnosis code",
      },
      diagnosis_description: {
        value: null,
        status: "missing",
        source_type: "user",
        required: true,
        label: "Diagnosis description",
      },
    },
    policy_medical_necessity: {
      policy_link_id: {
        value: 88,
        status: "present",
        source_type: "database",
        required: true,
        label: "Policy link ID",
      },
      policy_url: {
        value: "https://example.com/aetna-62323",
        status: "present",
        source_type: "policy",
        required: true,
        label: "Policy URL",
      },
      stored_rules_available: {
        value: true,
        status: "derived",
        source_type: "policy",
        required: true,
        label: "Stored rules available",
      },
      radiculopathy_evidence: {
        value: "Lumbar radicular pain documented.",
        status: "present",
        source_type: "user",
        required: true,
        label: "Lumbar / radicular symptoms",
      },
      dermatomal_distribution: {
        value: "Right L5 distribution",
        status: "present",
        source_type: "user",
        required: true,
        label: "Dermatomal distribution",
      },
      functional_limitation: {
        value: "Cannot sit longer than 15 minutes.",
        status: "present",
        source_type: "user",
        required: true,
        label: "Functional limitation",
      },
      conservative_treatment_failed: {
        value: "PT and NSAIDs failed over 6 weeks.",
        status: "present",
        source_type: "user",
        required: true,
        label: "Failed conservative treatment",
      },
      imaging_guidance: {
        value: "Fluoroscopy planned",
        status: "present",
        source_type: "policy",
        required: true,
        label: "Imaging guidance fluoroscopy / CT",
      },
      MRI_or_CT_or_EMG_evidence: {
        value: "MRI confirms nerve root irritation.",
        status: "present",
        source_type: "user",
        required: true,
        label: "MRI / CT or EMG evidence",
      },
      neuro_exam_evidence: {
        value: null,
        status: "missing",
        source_type: "user",
        required: true,
        label: "Neuro exam evidence",
      },
      frequency_session_limits_respected: {
        value: "Within payer limit",
        status: "derived",
        source_type: "policy",
        required: true,
        label: "Session / frequency limits",
      },
      radiologic_findings_consistent: null,
      initial_therapeutic_tfesi: null,
      vertebral_level_limits_respected: {
        value: "Single lumbar level",
        status: "derived",
        source_type: "policy",
        required: false,
        label: "Level limits",
      },
    },
    readiness: {
      ready_to_draft: false,
      missing_fields: ["policy_medical_necessity.neuro_exam_evidence"],
      blocking_reasons: ["Checklist is missing required fields."],
      next_questions: [
        "What neuro exam findings within the prior 3 months are documented?",
      ],
    },
  },
  filled: [
    {
      key: "patient_id",
      label: "Patient",
      status: "present",
      value: "DAVID R WIENTZEN",
      source_type: "database",
    },
  ],
  missing: [
    {
      key: "clinical.neuro_exam",
      label: "Recent neuro exam findings",
      status: "missing",
      value: null,
      source_type: "user",
    },
  ],
  needs_review: [],
  policy_constraints: [
    {
      key: "policy.clinical.radiculopathy",
      label: "Radiculopathy symptoms",
      status: "derived",
      value: "Document radiculopathy with dermatomal pain or symptoms.",
      source_type: "policy",
    },
  ],
  missing_fields: [
    {
      key: "clinical.neuro_exam",
      label: "Recent neuro exam findings",
      question: "What neuro exam findings within the prior 3 months are documented?",
    },
  ],
  follow_up_questions: [
    {
      question_key: "clinical.neuro_exam",
      prompt: "What neuro exam findings within the prior 3 months are documented?",
      status: "open",
    },
  ],
  updated_at: "2026-04-24T00:00:00",
};

test("renders structured virtual claim checklist and readiness", () => {
  render(<VirtualClaimPanel virtualClaim={draft} isLoading={false} error={null} />);

  expect(screen.getByText("Virtual Claim")).toBeInTheDocument();
  expect(screen.getAllByText(/Ready to draft: NO/i).length).toBeGreaterThan(0);
  expect(screen.getAllByText("DAVID R WIENTZEN").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Aetna").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Patient").length).toBeGreaterThan(0);
  expect(screen.getByText("Payer / Insurance")).toBeInTheDocument();
  expect(screen.getByText("Medical Necessity")).toBeInTheDocument();
  expect(screen.getByText("Aetna 62323 Policy Cheat-Sheet")).toBeInTheDocument();
  expect(screen.getAllByText("Neuro exam evidence").length).toBeGreaterThan(0);
  expect(
    screen.getByText("What neuro exam findings within the prior 3 months are documented?")
  ).toBeInTheDocument();
});

test("renders empty state when virtual claim data is absent", () => {
  render(<VirtualClaimPanel virtualClaim={null} isLoading={false} error={null} />);

  expect(screen.getByText("Virtual Claim")).toBeInTheDocument();
  expect(
    screen.getByText(/Start chatting to build the virtual claim checklist/i)
  ).toBeInTheDocument();
});
