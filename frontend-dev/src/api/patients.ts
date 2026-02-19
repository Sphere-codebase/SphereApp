import { z } from "zod";

import { requestJson } from "@/lib/api/client";
import type {
  PatientClaimsResponseDTO,
  PatientDetailDTO,
  PatientListResponseDTO,
} from "@/types/patients";

const patientListItemSchema = z.object({
  id: z.number(),
  first_name: z.string().nullable().optional(),
  last_name: z.string().nullable().optional(),
  date_of_birth: z.string().nullable().optional(),
  chart_number: z.string().nullable().optional(),
  primary_phone: z.string().nullable().optional(),
  doctor_id: z.number().nullable().optional(),
  doctor_name: z.string().nullable().optional(),
});

const patientListResponseSchema = z.object({
  items: z.array(patientListItemSchema),
  limit: z.number(),
  offset: z.number(),
  total: z.number(),
});

const patientAddressSchema = z.object({
  line1: z.string(),
  line2: z.string().nullable().optional(),
  city: z.string(),
  state: z.string().nullable().optional(),
  zip: z.string().nullable().optional(),
  country: z.string().nullable().optional(),
});

const patientDetailSchema = z.object({
  id: z.number(),
  first_name: z.string().nullable().optional(),
  last_name: z.string().nullable().optional(),
  date_of_birth: z.string().nullable().optional(),
  gender: z.string().nullable().optional(),
  chart_number: z.string().nullable().optional(),
  primary_phone: z.string().nullable().optional(),
  secondary_phone: z.string().nullable().optional(),
  address: patientAddressSchema.nullable().optional(),
  doctor_id: z.number().nullable().optional(),
});

const patientClaimItemSchema = z.object({
  id: z.number(),
  service_date: z.string().nullable().optional(),
  claim_status: z.enum(["draft", "final"]),
  insurance_company_name: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

const patientClaimsResponseSchema = z.object({
  items: z.array(patientClaimItemSchema),
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

export async function listPatients(params?: {
  query?: string;
  limit?: number;
  offset?: number;
}): Promise<PatientListResponseDTO> {
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
  const data = await requestJson<unknown>(`/api/patients${suffix ? `?${suffix}` : ""}`);
  return parseWithSchema(patientListResponseSchema, data, "list patients");
}

export async function getPatient(patientId: number): Promise<PatientDetailDTO> {
  const data = await requestJson<unknown>(`/api/patients/${patientId}`);
  return parseWithSchema(patientDetailSchema, data, "get patient");
}

export async function getPatientClaims(
  patientId: number,
  params?: { limit?: number; offset?: number }
): Promise<PatientClaimsResponseDTO> {
  const search = new URLSearchParams();
  if (typeof params?.limit === "number") {
    search.set("limit", String(params.limit));
  }
  if (typeof params?.offset === "number") {
    search.set("offset", String(params.offset));
  }
  const suffix = search.toString();
  const data = await requestJson<unknown>(
    `/api/patients/${patientId}/claims${suffix ? `?${suffix}` : ""}`
  );
  return parseWithSchema(patientClaimsResponseSchema, data, "patient claims");
}
