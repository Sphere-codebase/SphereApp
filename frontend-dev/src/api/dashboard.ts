import { z } from "zod";

import { requestJson } from "@/lib/api/client";
import type {
  DashboardClaimDTO,
  DashboardSessionDTO,
  DoctorDashboardDTO,
} from "@/types/dashboard";

const sessionSchema = z.object({
  id: z.number(),
  title: z.string().nullable().optional(),
  updated_at: z.string(),
});

const claimSchema = z.object({
  id: z.number(),
  patient_name: z.string(),
  service_date: z.string().nullable().optional(),
  claim_status: z.string(),
  insurance_company_name: z.string().nullable().optional(),
  updated_at: z.string(),
});

const dashboardSchema = z.object({
  doctor: z.object({
    id: z.number(),
    full_name: z.string().nullable().optional(),
  }),
  active_sessions: z.array(sessionSchema),
  recent_claims: z.array(claimSchema),
});

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

function toClaimStatus(value: string | null | undefined): "draft" | "final" {
  if (!value) {
    return "draft";
  }
  return value.toLowerCase() === "final" ? "final" : "draft";
}

function toSession(dto: z.infer<typeof sessionSchema>): DashboardSessionDTO {
  return {
    id: dto.id,
    title: dto.title ?? undefined,
    updated_at: dto.updated_at,
  };
}

function toClaim(dto: z.infer<typeof claimSchema>): DashboardClaimDTO {
  return {
    id: dto.id,
    patient_name: dto.patient_name,
    service_date: dto.service_date ?? undefined,
    claim_status: toClaimStatus(dto.claim_status),
    insurance_company_name: dto.insurance_company_name ?? undefined,
    updated_at: dto.updated_at,
  };
}

export async function getDoctorDashboard(): Promise<DoctorDashboardDTO> {
  const data = await requestJson<unknown>("/api/dashboard/doctor");
  const parsed = parseWithSchema(dashboardSchema, data, "doctor dashboard");
  return {
    doctor: {
      id: parsed.doctor.id,
      full_name: parsed.doctor.full_name ?? undefined,
    },
    active_sessions: parsed.active_sessions.map(toSession),
    recent_claims: parsed.recent_claims.map(toClaim),
  };
}
