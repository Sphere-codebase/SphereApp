import { z } from "zod";

import { requestJson } from "@/lib/api/client";
import type { VirtualClaimDTO, VirtualClaimMaterializeDTO } from "@/types/virtualClaim";

const virtualClaimFieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: z.enum(["missing", "present", "derived", "needs_review"]),
  value: z.unknown().nullable().optional(),
  source_type: z.enum(["database", "user", "llm_extracted", "derived", "policy"]),
});

const virtualClaimMissingFieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  question: z.string(),
});

const virtualClaimQuestionSchema = z.object({
  question_key: z.string(),
  prompt: z.string(),
  status: z.enum(["open", "answered", "dismissed"]),
  answer: z.unknown().nullable().optional(),
});

const virtualClaimPartySchema = z.object({
  id: z.number().nullable().optional(),
  name: z.string().nullable().optional(),
  date_of_birth: z.string().nullable().optional(),
});

const virtualClaimProcedureSchema = z.object({
  code: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
});

const virtualClaimPolicySummarySchema = z.object({
  policy_link_id: z.number().nullable().optional(),
  policy_rule_id: z.number().nullable().optional(),
  policy_url: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  extracted_at: z.string().nullable().optional(),
  rules_json: z.unknown().nullable().optional(),
  criteria_json: z.unknown().nullable().optional(),
  notes_json: z.unknown().nullable().optional(),
});

const virtualClaimSchema = z.object({
  draft_id: z.number(),
  session_id: z.number(),
  status: z.enum(["open", "ready", "materialized", "archived"]),
  readiness: z.boolean(),
  readiness_reason: z.string().nullable().optional(),
  patient: virtualClaimPartySchema.nullable().optional(),
  payer: virtualClaimPartySchema.nullable().optional(),
  procedure: virtualClaimProcedureSchema.nullable().optional(),
  materialized_claim_id: z.number().nullable().optional(),
  policy_summary: virtualClaimPolicySummarySchema.nullable().optional(),
  filled: z.array(virtualClaimFieldSchema),
  missing: z.array(virtualClaimFieldSchema),
  needs_review: z.array(virtualClaimFieldSchema),
  policy_constraints: z.array(virtualClaimFieldSchema),
  missing_fields: z.array(virtualClaimMissingFieldSchema),
  follow_up_questions: z.array(virtualClaimQuestionSchema),
  updated_at: z.string().nullable().optional(),
});

const virtualClaimMaterializeSchema = z.object({
  action_required: z.boolean(),
  proposal: z.record(z.string(), z.unknown()).nullable().optional(),
  claim_id: z.number().nullable().optional(),
  draft: virtualClaimSchema,
});

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

export async function ensureVirtualClaim(
  sessionId: number,
  payload: {
    patient_id?: number;
    insurance_company_id?: number;
    procedure_code?: string;
  } = {}
): Promise<VirtualClaimDTO> {
  const data = await requestJson<unknown>(`/api/chat/sessions/${sessionId}/virtual-claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseWithSchema(virtualClaimSchema, data, "ensure virtual claim");
}

export async function getVirtualClaim(sessionId: number): Promise<VirtualClaimDTO> {
  const data = await requestJson<unknown>(`/api/chat/sessions/${sessionId}/virtual-claim`);
  return parseWithSchema(virtualClaimSchema, data, "get virtual claim");
}

export async function patchVirtualClaim(
  sessionId: number,
  payload: {
    patient_id?: number;
    insurance_company_id?: number;
    procedure_code?: string;
    source_type?: "user" | "llm_extracted";
    fields?: Array<{ key: string; value: unknown }>;
  }
): Promise<VirtualClaimDTO> {
  const data = await requestJson<unknown>(`/api/chat/sessions/${sessionId}/virtual-claim`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseWithSchema(virtualClaimSchema, data, "patch virtual claim");
}

export async function recomputeVirtualClaim(sessionId: number): Promise<VirtualClaimDTO> {
  const data = await requestJson<unknown>(
    `/api/chat/sessions/${sessionId}/virtual-claim/recompute`,
    {
      method: "POST",
    }
  );
  return parseWithSchema(virtualClaimSchema, data, "recompute virtual claim");
}

export async function materializeVirtualClaim(
  sessionId: number,
  confirm = false
): Promise<VirtualClaimMaterializeDTO> {
  const data = await requestJson<unknown>(
    `/api/chat/sessions/${sessionId}/virtual-claim/materialize`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm }),
    }
  );
  return parseWithSchema(
    virtualClaimMaterializeSchema,
    data,
    "materialize virtual claim"
  );
}
