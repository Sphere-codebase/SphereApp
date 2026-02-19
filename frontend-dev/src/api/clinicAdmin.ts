import { z } from "zod";

import { requestJson } from "@/lib/api/client";
import type {
  ClinicAuditLogResponseDTO,
  ClinicDashboardDTO,
  ClinicDoctorsResponseDTO,
  DoctorUserDTO,
} from "@/types/clinicAdmin";

const doctorUserSchema = z.object({
  id: z.number(),
  email: z.string(),
  full_name: z.string().nullable().optional(),
  role: z.enum(["doctor", "chief_doctor", "clinic_admin", "platform_staff_admin"]),
  is_active: z.boolean(),
  created_at: z.string().nullable().optional(),
});

const doctorsListSchema = z.object({
  items: z.array(doctorUserSchema),
});

const auditLogItemSchema = z.object({
  id: z.number(),
  created_at: z.string().nullable().optional(),
  actor_id: z.number().nullable().optional(),
  actor_name: z.string().nullable().optional(),
  actor_role: z.string().nullable().optional(),
  action: z.string(),
  entity: z.string(),
  entity_id: z.string().nullable().optional(),
  diff_json: z.record(z.string(), z.unknown()).nullable().optional(),
  request_id: z.string().nullable().optional(),
});

const auditLogResponseSchema = z.object({
  items: z.array(auditLogItemSchema),
  limit: z.number(),
  offset: z.number(),
  total: z.number(),
});

const dashboardSchema = z.object({
  range: z.object({ from: z.string(), to: z.string() }),
  kpis: z.object({
    total_claims: z.number(),
    draft_claims: z.number(),
    finalized_claims: z.number(),
    active_doctors: z.number(),
  }),
  top_insurers: z.array(
    z.object({
      insurance_company_id: z.number(),
      name: z.string(),
      claim_count: z.number(),
    })
  ),
  claims_timeseries: z.array(z.object({ date: z.string(), count: z.number() })),
  ai_timeseries: z.array(z.object({ date: z.string(), count: z.number() })),
  recent_activity: z.array(auditLogItemSchema),
});

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

export async function getClinicDashboard(params?: {
  from?: string;
  to?: string;
}): Promise<ClinicDashboardDTO> {
  const search = new URLSearchParams();
  if (params?.from) {
    search.set("date_from", params.from);
  }
  if (params?.to) {
    search.set("date_to", params.to);
  }
  const suffix = search.toString();
  const data = await requestJson<unknown>(
    `/api/clinic/dashboard${suffix ? `?${suffix}` : ""}`
  );
  return parseWithSchema(dashboardSchema, data, "clinic dashboard");
}

export async function listClinicDoctors(): Promise<ClinicDoctorsResponseDTO> {
  const data = await requestJson<unknown>("/api/clinic/doctors");
  return parseWithSchema(doctorsListSchema, data, "clinic doctors");
}

export async function updateClinicDoctor(
  doctorId: number,
  payload: Partial<Pick<DoctorUserDTO, "role" | "is_active">>
): Promise<DoctorUserDTO> {
  const data = await requestJson<unknown>(`/api/clinic/doctors/${doctorId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseWithSchema(doctorUserSchema, data, "update doctor");
}

export async function listClinicAuditLogs(params: {
  from?: string;
  to?: string;
  actor_id?: number;
  entity?: string;
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<ClinicAuditLogResponseDTO> {
  const search = new URLSearchParams();
  if (params.from) {
    search.set("date_from", params.from);
  }
  if (params.to) {
    search.set("date_to", params.to);
  }
  if (typeof params.actor_id === "number") {
    search.set("actor_id", String(params.actor_id));
  }
  if (params.entity) {
    search.set("entity", params.entity);
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
    `/api/clinic/audit-logs${suffix ? `?${suffix}` : ""}`
  );
  return parseWithSchema(auditLogResponseSchema, data, "clinic audit logs");
}
