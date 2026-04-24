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
