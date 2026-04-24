import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

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

test("renders virtual claim readiness and follow-up questions", () => {
  render(
    <VirtualClaimPanel
      virtualClaim={draft}
      isLoading={false}
      error={null}
      onOpenUploadPdf={vi.fn()}
      onOpenCreateClaim={vi.fn()}
    />
  );

  expect(screen.getByText("Virtual Claim Checklist")).toBeInTheDocument();
  expect(screen.getByText("NOT READY")).toBeInTheDocument();
  expect(screen.getAllByText("DAVID R WIENTZEN").length).toBeGreaterThan(0);
  expect(screen.getByText("Aetna")).toBeInTheDocument();
  expect(screen.getByText("Recent neuro exam findings")).toBeInTheDocument();
  expect(
    screen.getByText("What neuro exam findings within the prior 3 months are documented?")
  ).toBeInTheDocument();
});
