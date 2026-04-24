export type VirtualClaimFieldStatus =
  | "missing"
  | "present"
  | "derived"
  | "needs_review";

export type VirtualClaimFieldSource =
  | "database"
  | "user"
  | "llm_extracted"
  | "derived"
  | "policy";

export interface VirtualClaimFieldDTO {
  key: string;
  label: string;
  status: VirtualClaimFieldStatus;
  value: unknown;
  source_type: VirtualClaimFieldSource;
}

export interface VirtualClaimMissingFieldDTO {
  key: string;
  label: string;
  question: string;
}

export interface VirtualClaimQuestionDTO {
  question_key: string;
  prompt: string;
  status: "open" | "answered" | "dismissed";
  answer?: unknown;
}

export interface VirtualClaimPartyDTO {
  id?: number | null;
  name?: string | null;
  date_of_birth?: string | null;
}

export interface VirtualClaimProcedureDTO {
  code?: string | null;
  description?: string | null;
}

export interface VirtualClaimPolicySummaryDTO {
  policy_link_id?: number | null;
  policy_rule_id?: number | null;
  policy_url?: string | null;
  title?: string | null;
  extracted_at?: string | null;
  rules_json?: unknown;
  criteria_json?: unknown;
  notes_json?: unknown;
}

export interface VirtualClaimChecklistValueDTO {
  value?: unknown;
  status: VirtualClaimFieldStatus;
  source_type: VirtualClaimFieldSource;
  required: boolean;
  label?: string | null;
}

export interface VirtualClaimPatientChecklistDTO {
  patient_id: VirtualClaimChecklistValueDTO;
  first_name: VirtualClaimChecklistValueDTO;
  last_name: VirtualClaimChecklistValueDTO;
  date_of_birth: VirtualClaimChecklistValueDTO;
}

export interface VirtualClaimPayerChecklistDTO {
  insurance_company_id: VirtualClaimChecklistValueDTO;
  payer_name: VirtualClaimChecklistValueDTO;
  member_id: VirtualClaimChecklistValueDTO;
  group_number: VirtualClaimChecklistValueDTO;
  policy_number: VirtualClaimChecklistValueDTO;
}

export interface VirtualClaimServiceChecklistDTO {
  procedure_code: VirtualClaimChecklistValueDTO;
  procedure_description: VirtualClaimChecklistValueDTO;
  service_date: VirtualClaimChecklistValueDTO;
  rendering_provider: VirtualClaimChecklistValueDTO;
  quantity: VirtualClaimChecklistValueDTO;
  modifier: VirtualClaimChecklistValueDTO;
}

export interface VirtualClaimDiagnosisChecklistDTO {
  diagnosis_code: VirtualClaimChecklistValueDTO;
  diagnosis_description: VirtualClaimChecklistValueDTO;
}

export interface VirtualClaimPolicyChecklistDTO {
  policy_link_id: VirtualClaimChecklistValueDTO;
  policy_url: VirtualClaimChecklistValueDTO;
  stored_rules_available: VirtualClaimChecklistValueDTO;
  radiculopathy_evidence: VirtualClaimChecklistValueDTO;
  dermatomal_distribution: VirtualClaimChecklistValueDTO;
  functional_limitation: VirtualClaimChecklistValueDTO;
  conservative_treatment_failed: VirtualClaimChecklistValueDTO;
  imaging_guidance: VirtualClaimChecklistValueDTO;
  MRI_or_CT_or_EMG_evidence: VirtualClaimChecklistValueDTO;
  neuro_exam_evidence: VirtualClaimChecklistValueDTO;
  frequency_session_limits_respected: VirtualClaimChecklistValueDTO;
  radiologic_findings_consistent?: VirtualClaimChecklistValueDTO | null;
  initial_therapeutic_tfesi?: VirtualClaimChecklistValueDTO | null;
  vertebral_level_limits_respected?: VirtualClaimChecklistValueDTO | null;
}

export interface VirtualClaimReadinessChecklistDTO {
  ready_to_draft: boolean;
  missing_fields: string[];
  blocking_reasons: string[];
  next_questions: string[];
}

export interface VirtualClaimChecklistDTO {
  patient: VirtualClaimPatientChecklistDTO;
  payer_insurance: VirtualClaimPayerChecklistDTO;
  service: VirtualClaimServiceChecklistDTO;
  diagnosis: VirtualClaimDiagnosisChecklistDTO;
  policy_medical_necessity: VirtualClaimPolicyChecklistDTO;
  readiness: VirtualClaimReadinessChecklistDTO;
}

export interface VirtualClaimDTO {
  draft_id: number;
  session_id: number;
  status: "open" | "ready" | "materialized" | "archived";
  readiness: boolean;
  readiness_reason?: string | null;
  patient?: VirtualClaimPartyDTO | null;
  payer?: VirtualClaimPartyDTO | null;
  procedure?: VirtualClaimProcedureDTO | null;
  materialized_claim_id?: number | null;
  policy_summary?: VirtualClaimPolicySummaryDTO | null;
  checklist: VirtualClaimChecklistDTO;
  filled: VirtualClaimFieldDTO[];
  missing: VirtualClaimFieldDTO[];
  needs_review: VirtualClaimFieldDTO[];
  policy_constraints: VirtualClaimFieldDTO[];
  missing_fields: VirtualClaimMissingFieldDTO[];
  follow_up_questions: VirtualClaimQuestionDTO[];
  updated_at?: string | null;
}

export interface VirtualClaimMaterializeDTO {
  action_required: boolean;
  proposal?: Record<string, unknown> | null;
  claim_id?: number | null;
  draft: VirtualClaimDTO;
}
