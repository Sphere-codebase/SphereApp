import { z } from "zod";

import { requestBlob, requestJson } from "@/lib/api/client";
import type {
  PlatformAuditResponseDTO,
  PlatformClinicsResponseDTO,
  PlatformClinicDTO,
  PlatformUsageDTO,
} from "@/types/platformAdmin";

const clinicCountersSchema = z.object({
  doctors_count: z.number().nullable().optional(),
  patients_count: z.number().nullable().optional(),
  claims_30d: z.number().nullable().optional(),
});

const clinicSchema = z.object({
  id: z.number(),
  name: z.string(),
  phone: z.string().nullable().optional(),
  billing_provider_npi: z.string().nullable().optional(),
  billing_provider_tax_id: z.string().nullable().optional(),
  billing_provider_organization_name: z.string().nullable().optional(),
  is_blocked: z.boolean().nullable().optional(),
  created_at: z.string().nullable().optional(),
  counters: clinicCountersSchema.nullable().optional(),
});

const clinicsResponseSchema = z.object({
  items: z.array(clinicSchema),
  limit: z.number(),
  offset: z.number(),
  total: z.number(),
});

const platformAuditItemSchema = z.object({
  id: z.number(),
  created_at: z.string().nullable().optional(),
  clinic_id: z.number(),
  clinic_name: z.string().nullable().optional(),
  actor_id: z.number().nullable().optional(),
  actor_name: z.string().nullable().optional(),
  actor_role: z.string().nullable().optional(),
  action: z.string(),
  entity: z.string(),
  entity_id: z.string().nullable().optional(),
  diff_json: z.record(z.string(), z.unknown()).nullable().optional(),
  request_id: z.string().nullable().optional(),
});

const platformAuditResponseSchema = z.object({
  items: z.array(platformAuditItemSchema),
  limit: z.number(),
  offset: z.number(),
  total: z.number(),
});

const usageSchema = z.object({
  range: z.object({ from: z.string(), to: z.string() }),
  scope: z.object({ clinic_id: z.number().nullable().optional() }),
  kpis: z.object({
    claims_created: z.number(),
    claims_finalized: z.number(),
    pdf_generated: z.number(),
    ai_actions: z.number(),
    active_clinics: z.number(),
  }),
  timeseries: z.object({
    claims: z.array(z.object({ date: z.string(), count: z.number() })),
    pdf: z.array(z.object({ date: z.string(), count: z.number() })),
    ai: z.array(z.object({ date: z.string(), count: z.number() })),
  }),
  top_clinics: z.array(
    z.object({
      clinic_id: z.number(),
      clinic_name: z.string(),
      claims: z.number(),
      pdf: z.number(),
      ai: z.number(),
    })
  ),
});

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

export async function listPlatformClinics(params?: {
  query?: string;
  limit?: number;
  offset?: number;
}): Promise<PlatformClinicsResponseDTO> {
  const search = new URLSearchParams();
  if (params?.query) {
    search.set("query", params.query);
  }
  if (typeof params?.limit === "number") {
    search.set("limit", String(params.limit));
  }
  if (typeof params?.offset === "number") {
    search.set("offset", String(params.offset));
  }
  const suffix = search.toString();
  const data = await requestJson<unknown>(
    `/api/platform/clinics${suffix ? `?${suffix}` : ""}`
  );
  return parseWithSchema(clinicsResponseSchema, data, "platform clinics");
}

export async function createPlatformClinic(payload: {
  name: string;
  phone?: string | null;
  billing_provider_npi?: string | null;
  billing_provider_tax_id?: string | null;
  billing_provider_organization_name?: string | null;
  address?: {
    line1?: string | null;
    line2?: string | null;
    city?: string | null;
    state?: string | null;
    zip?: string | null;
    country?: string | null;
  } | null;
}): Promise<PlatformClinicDTO> {
  const data = await requestJson<unknown>("/api/platform/clinics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseWithSchema(clinicSchema, data, "create clinic");
}

export async function updatePlatformClinic(
  clinicId: number,
  payload: {
    is_blocked?: boolean;
    phone?: string | null;
    billing_provider_npi?: string | null;
    billing_provider_tax_id?: string | null;
    billing_provider_organization_name?: string | null;
  }
): Promise<PlatformClinicDTO> {
  const data = await requestJson<unknown>(`/api/platform/clinics/${clinicId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseWithSchema(clinicSchema, data, "update clinic");
}

export async function listPlatformAudit(params: {
  clinic_id?: number;
  from?: string;
  to?: string;
  entity?: string;
  actor_id?: number;
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<PlatformAuditResponseDTO> {
  const search = new URLSearchParams();
  if (typeof params.clinic_id === "number") {
    search.set("clinic_id", String(params.clinic_id));
  }
  if (params.from) {
    search.set("date_from", params.from);
  }
  if (params.to) {
    search.set("date_to", params.to);
  }
  if (params.entity) {
    search.set("entity", params.entity);
  }
  if (typeof params.actor_id === "number") {
    search.set("actor_id", String(params.actor_id));
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
  const data = await requestJson<unknown>(
    `/api/platform/audit${suffix ? `?${suffix}` : ""}`
  );
  return parseWithSchema(platformAuditResponseSchema, data, "platform audit");
}

export async function exportPlatformAudit(params: {
  clinic_id?: number;
  from?: string;
  to?: string;
  entity?: string;
  actor_id?: number;
  action?: string;
  include_diff?: boolean;
}): Promise<{ blob: Blob; filename: string | null }> {
  const search = new URLSearchParams();
  if (typeof params.clinic_id === "number") {
    search.set("clinic_id", String(params.clinic_id));
  }
  if (params.from) {
    search.set("from", params.from);
  }
  if (params.to) {
    search.set("to", params.to);
  }
  if (params.entity) {
    search.set("entity", params.entity);
  }
  if (typeof params.actor_id === "number") {
    search.set("actor_id", String(params.actor_id));
  }
  if (params.action) {
    search.set("action", params.action);
  }
  search.set("include_diff", params.include_diff ? "1" : "0");
  const suffix = search.toString();
  const result = await requestBlob(
    `/api/platform/audit/export${suffix ? `?${suffix}` : ""}`
  );
  return { blob: result.blob, filename: result.filename };
}

export async function getPlatformUsage(params?: {
  from?: string;
  to?: string;
  clinic_id?: number | null;
}): Promise<PlatformUsageDTO> {
  const search = new URLSearchParams();
  if (params?.from) {
    search.set("date_from", params.from);
  }
  if (params?.to) {
    search.set("date_to", params.to);
  }
  if (typeof params?.clinic_id === "number") {
    search.set("clinic_id", String(params.clinic_id));
  }
  const suffix = search.toString();
  const data = await requestJson<unknown>(
    `/api/platform/usage${suffix ? `?${suffix}` : ""}`
  );
  return parseWithSchema(usageSchema, data, "platform usage");
}
