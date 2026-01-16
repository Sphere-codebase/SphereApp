import { z } from "zod";

import { requestJson, requestVoid } from "@/lib/api/client";

import {
  adminClaimDetailSchema,
  adminClaimSummarySchema,
  adminPatientSchema,
  adminUserSchema,
  diagnosisCodeSchema,
  insuranceCompanySchema,
  mcpCodeSchema,
  policyLinkSchema,
  type AdminClaimDetail,
  type AdminClaimSummary,
  type AdminPatient,
  type AdminUser,
  type AdminUserCreateInput,
  type AdminUserResetInput,
  type AdminUserUpdateInput,
  type DiagnosisCode,
  type DiagnosisCodeCreateInput,
  type DiagnosisCodeUpdateInput,
  type InsuranceCompany,
  type InsuranceCompanyCreateInput,
  type InsuranceCompanyUpdateInput,
  type McpCode,
  type McpCodeCreateInput,
  type McpCodeUpdateInput,
  type PolicyLink,
  type PolicyLinkCreateInput,
  type PolicyLinkUpdateInput,
} from "./schemas";

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

const insuranceCompaniesSchema = z.array(insuranceCompanySchema);
const mcpCodesSchema = z.array(mcpCodeSchema);
const diagnosisCodesSchema = z.array(diagnosisCodeSchema);
const policyLinksSchema = z.array(policyLinkSchema);
const adminUsersSchema = z.array(adminUserSchema);
const adminPatientsSchema = z.array(adminPatientSchema);
const adminClaimsSchema = z.array(adminClaimSummarySchema);

export async function listInsuranceCompanies(): Promise<InsuranceCompany[]> {
  const data = await requestJson<unknown>("/api/admin/insurance-companies");
  return parseWithSchema(insuranceCompaniesSchema, data, "list insurance companies");
}

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function apiUrl(path: string) {
  if (!API_BASE) return path; // use Vite proxy
  return `${API_BASE}${path}`;
}


export async function createInsuranceCompany(
  input: InsuranceCompanyCreateInput
): Promise<InsuranceCompany> {
  const data = await requestJson<unknown>("/api/admin/insurance-companies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(insuranceCompanySchema, data, "create insurance company");
}

export async function updateInsuranceCompany(
  id: number,
  input: InsuranceCompanyUpdateInput
): Promise<InsuranceCompany> {
  const data = await requestJson<unknown>(`/api/admin/insurance-companies/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(insuranceCompanySchema, data, "update insurance company");
}

export async function deleteInsuranceCompany(id: number): Promise<void> {
  await requestVoid(`/api/admin/insurance-companies/${id}`, { method: "DELETE" });
}

export async function listMcpCodes(query?: string): Promise<McpCode[]> {
  const data = await requestJson<unknown>(`/api/admin/mcp-codes${buildQuery({ query })}`);
  return parseWithSchema(mcpCodesSchema, data, "list mcp codes");
}

export async function createMcpCode(input: McpCodeCreateInput): Promise<McpCode> {
  const data = await requestJson<unknown>("/api/admin/mcp-codes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(mcpCodeSchema, data, "create mcp code");
}

export async function updateMcpCode(
  code: string,
  input: McpCodeUpdateInput
): Promise<McpCode> {
  const data = await requestJson<unknown>(`/api/admin/mcp-codes/${code}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(mcpCodeSchema, data, "update mcp code");
}

export async function deleteMcpCode(code: string): Promise<void> {
  await requestVoid(`/api/admin/mcp-codes/${code}`, { method: "DELETE" });
}

export async function listDiagnosisCodes(query?: string): Promise<DiagnosisCode[]> {
  const data = await requestJson<unknown>(
    `/api/admin/diagnosis-codes${buildQuery({ query })}`
  );
  return parseWithSchema(diagnosisCodesSchema, data, "list diagnosis codes");
}

export async function createDiagnosisCode(
  input: DiagnosisCodeCreateInput
): Promise<DiagnosisCode> {
  const data = await requestJson<unknown>("/api/admin/diagnosis-codes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(diagnosisCodeSchema, data, "create diagnosis code");
}

export async function updateDiagnosisCode(
  code: string,
  input: DiagnosisCodeUpdateInput
): Promise<DiagnosisCode> {
  const data = await requestJson<unknown>(`/api/admin/diagnosis-codes/${code}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(diagnosisCodeSchema, data, "update diagnosis code");
}

export async function deleteDiagnosisCode(code: string): Promise<void> {
  await requestVoid(`/api/admin/diagnosis-codes/${code}`, { method: "DELETE" });
}

export async function listPolicyLinks(filters: {
  insurance_company_id?: number;
  mcp_code?: string;
  query?: string;
}): Promise<PolicyLink[]> {
  const data = await requestJson<unknown>(
    `/api/admin/policy-links${buildQuery(filters)}`
  );
  return parseWithSchema(policyLinksSchema, data, "list policy links");
}

export async function createPolicyLink(
  input: PolicyLinkCreateInput
): Promise<PolicyLink> {
  const data = await requestJson<unknown>("/api/admin/policy-links", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(policyLinkSchema, data, "create policy link");
}

export async function updatePolicyLink(
  id: number,
  input: PolicyLinkUpdateInput
): Promise<PolicyLink> {
  const data = await requestJson<unknown>(`/api/admin/policy-links/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(policyLinkSchema, data, "update policy link");
}

export async function deletePolicyLink(id: number): Promise<void> {
  await requestVoid(`/api/admin/policy-links/${id}`, { method: "DELETE" });
}

export async function listAdminUsers(filters: {
  query?: string;
  is_active?: boolean;
  role?: string;
}): Promise<AdminUser[]> {
  const data = await requestJson<unknown>(
    `/api/admin/users${buildQuery({
      query: filters.query,
      is_active: filters.is_active === undefined ? undefined : String(filters.is_active),
      role: filters.role,
    })}`
  );
  return parseWithSchema(adminUsersSchema, data, "list admin users");
}

export async function createAdminUser(input: AdminUserCreateInput): Promise<AdminUser> {
  const data = await requestJson<unknown>("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(adminUserSchema, data, "create admin user");
}

export async function updateAdminUser(
  id: number,
  input: AdminUserUpdateInput
): Promise<AdminUser> {
  const data = await requestJson<unknown>(`/api/admin/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(adminUserSchema, data, "update admin user");
}

export async function resetAdminUserPassword(
  id: number,
  input: AdminUserResetInput
): Promise<void> {
  await requestVoid(`/api/admin/users/${id}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listAdminPatients(query?: string): Promise<AdminPatient[]> {
  const data = await requestJson<unknown>(
    `/api/admin/patients${buildQuery({ query })}`
  );
  return parseWithSchema(adminPatientsSchema, data, "list admin patients");
}

export async function listAdminClaims(filters: {
  patient_id?: number;
  insurance_company_id?: number;
  status?: string;
  service_from?: string;
  service_to?: string;
}): Promise<AdminClaimSummary[]> {
  const data = await requestJson<unknown>(
    `/api/admin/claims${buildQuery(filters)}`
  );
  return parseWithSchema(adminClaimsSchema, data, "list admin claims");
}

export async function getAdminClaimDetail(id: number): Promise<AdminClaimDetail> {
  const data = await requestJson<unknown>(`/api/admin/claims/${id}`);
  return parseWithSchema(adminClaimDetailSchema, data, "claim detail");
}

export type {
  AdminClaimDetail,
  AdminClaimSummary,
  AdminPatient,
  AdminUser,
  AdminUserCreateInput,
  AdminUserResetInput,
  AdminUserUpdateInput,
  DiagnosisCode,
  DiagnosisCodeCreateInput,
  DiagnosisCodeUpdateInput,
  InsuranceCompany,
  InsuranceCompanyCreateInput,
  InsuranceCompanyUpdateInput,
  McpCode,
  McpCodeCreateInput,
  McpCodeUpdateInput,
  PolicyLink,
  PolicyLinkCreateInput,
  PolicyLinkUpdateInput,
};
