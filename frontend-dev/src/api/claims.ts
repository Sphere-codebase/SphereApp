import { z } from "zod";

import type {
  ClaimDTO,
  ClaimFinancialSummaryDTO,
  DiagnosisCodeDTO,
  MCPCodeDTO,
  PatientDTO,
} from "@/types/claim";
import { requestJson, requestVoid } from "@/lib/api/client";

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

const patientSchema = z.object({
  id: z.number().optional(),
  first_name: z.string().nullable().optional(),
  last_name: z.string().nullable().optional(),
  date_of_birth: z.string().nullable().optional(),
});

const mcpCodeSchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

const diagnosisCodeSchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

const financialPredictionSchema = z.object({
  mcp_code: z.string(),
  predicted_paid_amount: z.number(),
  confidence: z.number().nullable().optional(),
  explanation: z.string().nullable().optional(),
  source: z.enum(["ml_predictions", "mcp_payment_predictions"]),
});

const financialFlagSchema = z.object({
  code: z.string(),
  severity: z.enum(["info", "warn", "high"]),
  message: z.string(),
});

const claimFinancialSummarySchema = z.object({
  claim_id: z.number(),
  currency: z.literal("USD"),
  predicted_total_paid_amount: z.number(),
  predicted_per_mcp: z.array(financialPredictionSchema),
  flags: z.array(financialFlagSchema),
  updated_at: z.string(),
});

const claimDetailSchema = z.object({
  id: z.number(),
  claim_status: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
  patient: patientSchema,
  insurance_company_id: z.number(),
  service_date: z.string().nullable().optional(),
  mcp_codes: z.array(mcpCodeSchema).optional(),
  diagnosis_codes: z.array(diagnosisCodeSchema).optional(),
});

const claimPdfResponseSchema = z.object({
  pdf_id: z.string(),
  pdf_url: z.string(),
});

const mcpCodesSchema = z.array(mcpCodeSchema);
const diagnosisCodesSchema = z.array(diagnosisCodeSchema);

export type ClaimDraftInput = {
  patient?: {
    first_name: string;
    last_name: string;
    date_of_birth?: string | null;
  };
  patient_id?: number | null;
  insurance_company_id: number;
  service_date: string;
  session_id?: number | null;
};

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

function toClaimStatus(value?: string | null): "draft" | "final" {
  if (!value) {
    return "draft";
  }
  return value.toUpperCase() === "DRAFT" ? "draft" : "final";
}

function toPatient(dto: z.infer<typeof patientSchema>): PatientDTO {
  return {
    id: dto.id,
    first_name: dto.first_name ?? "",
    last_name: dto.last_name ?? "",
    date_of_birth: dto.date_of_birth ?? undefined,
  };
}

function toMcpCode(dto: z.infer<typeof mcpCodeSchema>): MCPCodeDTO {
  return {
    code: dto.code,
    description: dto.description ?? "",
  };
}

function toDiagnosisCode(dto: z.infer<typeof diagnosisCodeSchema>): DiagnosisCodeDTO {
  return {
    code: dto.code,
    description: dto.description ?? "",
  };
}

function toClaim(dto: z.infer<typeof claimDetailSchema>): ClaimDTO {
  return {
    id: dto.id,
    claim_status: toClaimStatus(dto.claim_status ?? null),
    patient: toPatient(dto.patient),
    insurance_company_id: dto.insurance_company_id,
    service_date: dto.service_date ?? "",
    mcp_codes: (dto.mcp_codes ?? []).map(toMcpCode),
    diagnosis_codes: (dto.diagnosis_codes ?? []).map(toDiagnosisCode),
  };
}

function toFinancialSummary(
  dto: z.infer<typeof claimFinancialSummarySchema>
): ClaimFinancialSummaryDTO {
  return dto;
}

export async function ingestPdf(
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

export async function createClaimDraft(payload: ClaimDraftInput): Promise<ClaimDTO> {
  const data = await requestJson<unknown>("/api/claims", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const created = parseWithSchema(
    z.object({ id: z.number() }),
    data,
    "create claim"
  );
  return getClaim(created.id);
}

export async function getClaim(claimId: number): Promise<ClaimDTO> {
  const data = await requestJson<unknown>(`/api/claims/${claimId}`);
  const parsed = parseWithSchema(claimDetailSchema, data, "get claim");
  return toClaim(parsed);
}

export async function getClaimFinancialSummary(
  claimId: number
): Promise<ClaimFinancialSummaryDTO> {
  const data = await requestJson<unknown>(`/api/claims/${claimId}/financial`);
  const parsed = parseWithSchema(
    claimFinancialSummarySchema,
    data,
    "claim financial summary"
  );
  return toFinancialSummary(parsed);
}

export async function refreshClaimFinancialSummary(
  claimId: number
): Promise<ClaimFinancialSummaryDTO> {
  const data = await requestJson<unknown>(`/api/claims/${claimId}/financial/refresh`, {
    method: "POST",
  });
  const parsed = parseWithSchema(
    claimFinancialSummarySchema,
    data,
    "claim financial refresh"
  );
  return toFinancialSummary(parsed);
}

export async function finalizeClaim(claimId: number): Promise<ClaimDTO> {
  const data = await requestJson<unknown>(`/api/claims/${claimId}/finalize`, {
    method: "POST",
  });
  const parsed = parseWithSchema(claimDetailSchema, data, "finalize claim");
  return toClaim(parsed);
}

export async function generateClaimPdf(
  claimId: number
): Promise<{ pdf_url: string; pdf_id: string }> {
  const data = await requestJson<unknown>(`/api/claims/${claimId}/pdf`, {
    method: "POST",
  });
  return parseWithSchema(claimPdfResponseSchema, data, "generate claim pdf");
}

export async function searchMcpCodes(query: string): Promise<MCPCodeDTO[]> {
  const data = await requestJson<unknown>(`/api/codes/mcp?query=${encodeURIComponent(query)}`);
  const parsed = parseWithSchema(mcpCodesSchema, data, "search mcp codes");
  return parsed.map(toMcpCode);
}

export async function searchDiagnosisCodes(query: string): Promise<DiagnosisCodeDTO[]> {
  const data = await requestJson<unknown>(
    `/api/codes/diagnosis?query=${encodeURIComponent(query)}`
  );
  const parsed = parseWithSchema(diagnosisCodesSchema, data, "search diagnosis codes");
  return parsed.map(toDiagnosisCode);
}

export async function addMcpCode(claimId: number, code: string): Promise<void> {
  await requestJson(`/api/claims/${claimId}/mcp-codes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
}

export async function removeMcpCode(claimId: number, code: string): Promise<void> {
  await requestVoid(`/api/claims/${claimId}/mcp-codes/${encodeURIComponent(code)}`, {
    method: "DELETE",
  });
}

export async function addDiagnosisCode(claimId: number, code: string): Promise<void> {
  await requestJson(`/api/claims/${claimId}/diagnosis-codes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
}

export async function removeDiagnosisCode(claimId: number, code: string): Promise<void> {
  await requestVoid(
    `/api/claims/${claimId}/diagnosis-codes/${encodeURIComponent(code)}`,
    {
      method: "DELETE",
    }
  );
}
