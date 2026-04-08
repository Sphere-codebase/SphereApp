import { z } from "zod";

import { requestJson } from "@/lib/api/client";
import type { AIHistoryResponseDTO } from "@/types/aiHistory";

const aiHistoryItemSchema = z.object({
  id: z.number(),
  created_at: z.string().nullable().optional(),
  actor_id: z.number().nullable().optional(),
  actor_name: z.string().nullable().optional(),
  action: z.string(),
  entity: z.string(),
  entity_id: z.string().nullable().optional(),
  diff_json: z.record(z.string(), z.unknown()).nullable().optional(),
  request_id: z.string().nullable().optional(),
});

const aiHistoryResponseSchema = z.object({
  items: z.array(aiHistoryItemSchema),
  limit: z.number(),
  offset: z.number(),
  total: z.number(),
});

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

export async function listAIHistory(params: {
  from?: string;
  to?: string;
  doctor_id?: number;
  claim_id?: number;
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<AIHistoryResponseDTO> {
  const search = new URLSearchParams();
  if (params.from) {
    search.set("date_from", params.from);
  }
  if (params.to) {
    search.set("date_to", params.to);
  }
  if (typeof params.doctor_id === "number") {
    search.set("actor_id", String(params.doctor_id));
  }
  if (typeof params.claim_id === "number") {
    search.set("claim_id", String(params.claim_id));
  }
  if (params.action) {
    search.set("action", params.action);
  }
  if (typeof params.limit === "number") {
    search.set("limit", String(params.limit));
  }
  if (typeof params.offset === "number") {
    search.set("offset", String(params.offset));
  }

  const suffix = search.toString();
  const data = await requestJson<unknown>(`/api/ai-history${suffix ? `?${suffix}` : ""}`);
  return parseWithSchema(aiHistoryResponseSchema, data, "AI history");
}
