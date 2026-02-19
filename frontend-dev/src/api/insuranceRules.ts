import { z } from "zod";

import { requestJson, requestVoid } from "@/lib/api/client";
import type {
  ClinicOverrideDTO,
  DoctorOverrideDTO,
  InsuranceCompanyDTO,
  PolicyLinkDTO,
  PolicyRulesDTO,
} from "@/types/insuranceRules";

const insuranceCompanySchema = z.object({
  id: z.number(),
  name: z.string(),
});

const insuranceCompanyListSchema = z.object({
  items: z.array(insuranceCompanySchema),
  limit: z.number(),
  offset: z.number(),
  total: z.number(),
});

const policyLinkSchema = z.object({
  id: z.number(),
  insurance_company_id: z.number(),
  mcp_code: z.string(),
  policy_url: z.string(),
});

const policyLinkListSchema = z.object({
  items: z.array(policyLinkSchema),
});

const policyRulesSchema = z.object({
  policy_link_id: z.number(),
  extracted_at: z.string().nullable().optional(),
  rules_json: z.unknown().nullable().optional(),
});

const clinicOverrideSchema = z.object({
  policy_link_id: z.number(),
  clinic_id: z.number(),
  override_json: z.record(z.string(), z.unknown()).nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

const doctorOverrideSchema = z.object({
  policy_link_id: z.number(),
  doctor_id: z.number(),
  override_json: z.record(z.string(), z.unknown()).nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

export async function listInsuranceCompanies(query?: string): Promise<InsuranceCompanyDTO[]> {
  const search = new URLSearchParams();
  if (query) {
    search.set("q", query);
  }
  const suffix = search.toString();
  const data = await requestJson<unknown>(
    `/api/insurance-companies${suffix ? `?${suffix}` : ""}`
  );
  const parsed = parseWithSchema(insuranceCompanyListSchema, data, "insurance companies");
  return parsed.items;
}

export async function listPolicyLinks(params: {
  insurance_company_id: number;
  mcp_code: string;
}): Promise<PolicyLinkDTO[]> {
  const search = new URLSearchParams();
  search.set("insurance_company_id", String(params.insurance_company_id));
  search.set("mcp_code", params.mcp_code);
  const data = await requestJson<unknown>(
    `/api/insurance-rules/policy-links?${search.toString()}`
  );
  const parsed = parseWithSchema(policyLinkListSchema, data, "policy links");
  return parsed.items;
}

export async function getPolicyRules(policyLinkId: number): Promise<PolicyRulesDTO> {
  const data = await requestJson<unknown>(`/api/insurance-rules/${policyLinkId}/rules`);
  return parseWithSchema(policyRulesSchema, data, "policy rules");
}

export async function getClinicOverride(
  policyLinkId: number
): Promise<ClinicOverrideDTO> {
  const data = await requestJson<unknown>(
    `/api/insurance-rules/${policyLinkId}/clinic-override`
  );
  return parseWithSchema(clinicOverrideSchema, data, "clinic override");
}

export async function upsertClinicOverride(
  policyLinkId: number,
  override_json: Record<string, unknown>
): Promise<ClinicOverrideDTO> {
  const data = await requestJson<unknown>(
    `/api/insurance-rules/${policyLinkId}/clinic-override`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ override_json }),
    }
  );
  return parseWithSchema(clinicOverrideSchema, data, "clinic override update");
}

export async function deleteClinicOverride(policyLinkId: number): Promise<void> {
  await requestVoid(`/api/insurance-rules/${policyLinkId}/clinic-override`, {
    method: "DELETE",
  });
}

export async function getDoctorOverride(
  policyLinkId: number
): Promise<DoctorOverrideDTO> {
  const data = await requestJson<unknown>(
    `/api/insurance-rules/${policyLinkId}/doctor-override`
  );
  return parseWithSchema(doctorOverrideSchema, data, "doctor override");
}

export async function upsertDoctorOverride(
  policyLinkId: number,
  override_json: Record<string, unknown>
): Promise<DoctorOverrideDTO> {
  const data = await requestJson<unknown>(
    `/api/insurance-rules/${policyLinkId}/doctor-override`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ override_json }),
    }
  );
  return parseWithSchema(doctorOverrideSchema, data, "doctor override update");
}

export async function deleteDoctorOverride(policyLinkId: number): Promise<void> {
  await requestVoid(`/api/insurance-rules/${policyLinkId}/doctor-override`, {
    method: "DELETE",
  });
}
