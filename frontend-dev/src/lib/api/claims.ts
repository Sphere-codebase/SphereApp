import { z } from "zod";

import { requestJson } from "@/lib/api/client";

const claimPdfIngestResponseSchema = z.object({
  claim_id: z.number(),
  patient_id: z.number(),
  session_id: z.number().nullable().optional(),
  patient_name: z.string(),
  patient_date_of_birth: z.string().nullable(),
  account_number: z.string().nullable(),
  service_date: z.string().nullable(),
  line_count: z.number(),
  total_billed_cents: z.number(),
  total_allowed_cents: z.number(),
  total_paid_cents: z.number(),
});

export type ClaimPdfIngestResponse = z.infer<typeof claimPdfIngestResponseSchema>;

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

export async function ingestClaimPdf(
  file: File,
  sessionId?: number | null
): Promise<ClaimPdfIngestResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (sessionId) {
    formData.append("session_id", String(sessionId));
  }
  const data = await requestJson<unknown>("/api/claims/ingest-pdf", {
    method: "POST",
    body: formData,
  });
  return parseWithSchema(claimPdfIngestResponseSchema, data, "claim pdf ingest");
}
