import { z } from "zod";

import { requestJson, requestVoid } from "@/lib/api/client";

import {
  adminClaimDetailSchema,
  adminClaimSummarySchema,
  adminPatientSchema,
  adminUserSchema,
  agencySchema,
  diagnosisSchema,
  policyLinkSchema,
  procedureCodeSchema,
  type AdminClaimDetail,
  type AdminClaimSummary,
  type AdminPatient,
  type AdminUser,
  type AdminUserCreateInput,
  type AdminUserResetInput,
  type AdminUserUpdateInput,
  type Agency,
  type AgencyCreateInput,
  type AgencyUpdateInput,
  type Diagnosis,
  type DiagnosisCreateInput,
  type DiagnosisUpdateInput,
  type PolicyLink,
  type PolicyLinkCreateInput,
  type PolicyLinkUpdateInput,
  type ProcedureCode,
  type ProcedureCodeCreateInput,
  type ProcedureCodeUpdateInput,
} from "./schemas";

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

function buildQuery(params: Record<string, string | null | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      query.set(key, value);
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

const agenciesSchema = z.array(agencySchema);
const procedureCodesSchema = z.array(procedureCodeSchema);
const diagnosesSchema = z.array(diagnosisSchema);
const policyLinksSchema = z.array(policyLinkSchema);
const adminUsersSchema = z.array(adminUserSchema);
const adminPatientsSchema = z.array(adminPatientSchema);
const adminClaimsSchema = z.array(adminClaimSummarySchema);

export async function listAgencies(): Promise<Agency[]> {
  const data = await requestJson<unknown>("/api/admin/agencies");
  return parseWithSchema(agenciesSchema, data, "list agencies");
}

export async function createAgency(input: AgencyCreateInput): Promise<Agency> {
  const data = await requestJson<unknown>("/api/admin/agencies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(agencySchema, data, "create agency");
}

export async function updateAgency(id: string, input: AgencyUpdateInput): Promise<Agency> {
  const data = await requestJson<unknown>(`/api/admin/agencies/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(agencySchema, data, "update agency");
}

export async function deleteAgency(id: string): Promise<void> {
  await requestVoid(`/api/admin/agencies/${id}`, { method: "DELETE" });
}

export async function listProcedureCodes(query?: string): Promise<ProcedureCode[]> {
  const data = await requestJson<unknown>(
    `/api/admin/procedure-codes${buildQuery({ query })}`
  );
  return parseWithSchema(procedureCodesSchema, data, "list procedure codes");
}

export async function createProcedureCode(
  input: ProcedureCodeCreateInput
): Promise<ProcedureCode> {
  const data = await requestJson<unknown>("/api/admin/procedure-codes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(procedureCodeSchema, data, "create procedure code");
}

export async function updateProcedureCode(
  id: string,
  input: ProcedureCodeUpdateInput
): Promise<ProcedureCode> {
  const data = await requestJson<unknown>(`/api/admin/procedure-codes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(procedureCodeSchema, data, "update procedure code");
}

export async function deleteProcedureCode(id: string): Promise<void> {
  await requestVoid(`/api/admin/procedure-codes/${id}`, { method: "DELETE" });
}

export async function listDiagnoses(query?: string): Promise<Diagnosis[]> {
  const data = await requestJson<unknown>(
    `/api/admin/diagnoses${buildQuery({ query })}`
  );
  return parseWithSchema(diagnosesSchema, data, "list diagnoses");
}

export async function createDiagnosis(input: DiagnosisCreateInput): Promise<Diagnosis> {
  const data = await requestJson<unknown>("/api/admin/diagnoses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(diagnosisSchema, data, "create diagnosis");
}

export async function updateDiagnosis(
  id: string,
  input: DiagnosisUpdateInput
): Promise<Diagnosis> {
  const data = await requestJson<unknown>(`/api/admin/diagnoses/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(diagnosisSchema, data, "update diagnosis");
}

export async function deleteDiagnosis(id: string): Promise<void> {
  await requestVoid(`/api/admin/diagnoses/${id}`, { method: "DELETE" });
}

export async function listPolicyLinks(filters: {
  agency_id?: string;
  procedure_code_id?: string;
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
  id: string,
  input: PolicyLinkUpdateInput
): Promise<PolicyLink> {
  const data = await requestJson<unknown>(`/api/admin/policy-links/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(policyLinkSchema, data, "update policy link");
}

export async function deletePolicyLink(id: string): Promise<void> {
  await requestVoid(`/api/admin/policy-links/${id}`, { method: "DELETE" });
}

export async function listAdminUsers(filters: {
  query?: string;
  is_active?: boolean;
  is_admin?: boolean;
}): Promise<AdminUser[]> {
  const data = await requestJson<unknown>(
    `/api/admin/users${buildQuery({
      query: filters.query,
      is_active: filters.is_active === undefined ? undefined : String(filters.is_active),
      is_admin: filters.is_admin === undefined ? undefined : String(filters.is_admin),
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
  id: string,
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
  id: string,
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
  patient_id?: string;
  agency_id?: string;
  status?: string;
  service_from?: string;
  service_to?: string;
}): Promise<AdminClaimSummary[]> {
  const data = await requestJson<unknown>(
    `/api/admin/claims${buildQuery(filters)}`
  );
  return parseWithSchema(adminClaimsSchema, data, "list admin claims");
}

export async function getAdminClaimDetail(id: string): Promise<AdminClaimDetail> {
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
  Agency,
  AgencyCreateInput,
  AgencyUpdateInput,
  Diagnosis,
  DiagnosisCreateInput,
  DiagnosisUpdateInput,
  PolicyLink,
  PolicyLinkCreateInput,
  PolicyLinkUpdateInput,
  ProcedureCode,
  ProcedureCodeCreateInput,
  ProcedureCodeUpdateInput,
};
