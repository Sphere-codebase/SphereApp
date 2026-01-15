import { z } from "zod";

const dateString = z.string();
const optionalDate = z.string().nullable().optional();

export const agencySchema = z.object({
  id: z.string(),
  name: z.string(),
  slug: z.string().nullable(),
  is_active: z.boolean(),
  created_at: dateString,
  updated_at: dateString,
});

export const agencyCreateSchema = z.object({
  name: z.string(),
  slug: z.string().nullable().optional(),
  is_active: z.boolean().optional(),
});

export const agencyUpdateSchema = agencyCreateSchema.partial();

export const procedureCodeSchema = z.object({
  id: z.string(),
  code: z.string(),
  title: z.string().nullable().optional(),
  created_at: dateString,
  updated_at: dateString,
});

export const procedureCodeCreateSchema = z.object({
  code: z.string(),
  title: z.string().nullable().optional(),
});

export const procedureCodeUpdateSchema = procedureCodeCreateSchema.partial();

export const diagnosisSchema = z.object({
  id: z.string(),
  code: z.string(),
  title: z.string().nullable().optional(),
  created_at: dateString,
  updated_at: dateString,
});

export const diagnosisCreateSchema = z.object({
  code: z.string(),
  title: z.string().nullable().optional(),
});

export const diagnosisUpdateSchema = diagnosisCreateSchema.partial();

export const policyLinkSchema = z.object({
  id: z.string(),
  agency_id: z.string(),
  procedure_code_id: z.string(),
  policy_url: z.string().url(),
  effective_from: optionalDate,
  effective_to: optionalDate,
  status: z.enum(["ACTIVE", "INACTIVE"]),
  notes: z.string().nullable().optional(),
  created_at: dateString,
  updated_at: dateString,
});

export const policyLinkCreateSchema = z.object({
  agency_id: z.string(),
  procedure_code_id: z.string(),
  policy_url: z.string(),
  effective_from: z.string().nullable().optional(),
  effective_to: z.string().nullable().optional(),
  status: z.enum(["ACTIVE", "INACTIVE"]),
  notes: z.string().nullable().optional(),
});

export const policyLinkUpdateSchema = policyLinkCreateSchema.partial();

export const adminUserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  full_name: z.string().nullable(),
  tenant_id: z.string(),
  is_active: z.boolean(),
  is_admin: z.boolean(),
  created_at: dateString,
});

export const adminUserCreateSchema = z.object({
  email: z.string().email(),
  full_name: z.string().nullable().optional(),
  password: z.string(),
  is_admin: z.boolean(),
  is_active: z.boolean(),
});

export const adminUserUpdateSchema = z.object({
  email: z.string().email().nullable().optional(),
  full_name: z.string().nullable().optional(),
  is_admin: z.boolean().optional(),
  is_active: z.boolean().optional(),
});

export const adminUserResetSchema = z.object({
  password: z.string(),
});

export const adminPatientSchema = z.object({
  id: z.string(),
  user_id: z.string().nullable(),
  first_name: z.string().nullable(),
  last_name: z.string().nullable(),
  full_name: z.string(),
  date_of_birth: z.string().nullable(),
  sex: z.string().nullable(),
  created_at: dateString,
  updated_at: dateString,
});

export const claimStatusSchema = z.enum(["DRAFT", "SUBMITTED", "PAID", "DENIED"]);

export const adminClaimSummarySchema = z.object({
  id: z.string(),
  patient_id: z.string(),
  patient_name: z.string(),
  patient_user_id: z.string().nullable(),
  agency_id: z.string().nullable(),
  agency_name: z.string().nullable(),
  claim_number: z.string().nullable(),
  status: claimStatusSchema,
  service_from: z.string().nullable(),
  service_to: z.string().nullable(),
  received_at: z.string().nullable(),
  finalized_at: z.string().nullable(),
  billed_total_cents: z.number().int().nullable(),
  allowed_total_cents: z.number().int().nullable(),
  paid_total_cents: z.number().int().nullable(),
  patient_responsibility_cents: z.number().int().nullable(),
  created_at: dateString,
  updated_at: dateString,
});

export const procedureCodeSummarySchema = z.object({
  id: z.string(),
  code: z.string(),
  title: z.string().nullable(),
});

export const adminClaimProcedurePaymentSchema = z.object({
  id: z.string(),
  paid_amount_cents: z.number().int(),
  adjustment_amount_cents: z.number().int().nullable(),
  adjustment_reason_code: z.string().nullable(),
  check_number: z.string().nullable(),
  paid_at: z.string(),
  created_at: z.string(),
});

export const adminClaimProcedureSchema = z.object({
  id: z.string(),
  procedure_code: procedureCodeSummarySchema,
  units: z.number().int(),
  modifier: z.string().nullable(),
  price: z.number().nullable(),
  billed_amount_cents: z.number().int().nullable(),
  allowed_amount_cents: z.number().int().nullable(),
  coinsurance_amount_cents: z.number().int().nullable(),
  copay_amount_cents: z.number().int().nullable(),
  deductible_amount_cents: z.number().int().nullable(),
  paid_amount_cents: z.number().int().nullable(),
  denial_reason_code: z.string().nullable(),
  line_number: z.number().int().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  payments: z.array(adminClaimProcedurePaymentSchema),
});

export const adminDiagnosisSummarySchema = z.object({
  id: z.string(),
  code: z.string(),
  title: z.string().nullable(),
});

export const adminClaimDetailSchema = z.object({
  id: z.string(),
  patient: adminPatientSchema,
  agency: agencySchema.nullable(),
  claim_number: z.string().nullable(),
  status: claimStatusSchema,
  service_from: z.string().nullable(),
  service_to: z.string().nullable(),
  received_at: z.string().nullable(),
  finalized_at: z.string().nullable(),
  billed_total_cents: z.number().int().nullable(),
  allowed_total_cents: z.number().int().nullable(),
  paid_total_cents: z.number().int().nullable(),
  patient_responsibility_cents: z.number().int().nullable(),
  created_at: dateString,
  updated_at: dateString,
  procedures: z.array(adminClaimProcedureSchema),
  diagnoses: z.array(adminDiagnosisSummarySchema),
});

export type Agency = z.infer<typeof agencySchema>;
export type AgencyCreateInput = z.infer<typeof agencyCreateSchema>;
export type AgencyUpdateInput = z.infer<typeof agencyUpdateSchema>;
export type ProcedureCode = z.infer<typeof procedureCodeSchema>;
export type ProcedureCodeCreateInput = z.infer<typeof procedureCodeCreateSchema>;
export type ProcedureCodeUpdateInput = z.infer<typeof procedureCodeUpdateSchema>;
export type Diagnosis = z.infer<typeof diagnosisSchema>;
export type DiagnosisCreateInput = z.infer<typeof diagnosisCreateSchema>;
export type DiagnosisUpdateInput = z.infer<typeof diagnosisUpdateSchema>;
export type PolicyLink = z.infer<typeof policyLinkSchema>;
export type PolicyLinkCreateInput = z.infer<typeof policyLinkCreateSchema>;
export type PolicyLinkUpdateInput = z.infer<typeof policyLinkUpdateSchema>;
export type AdminUser = z.infer<typeof adminUserSchema>;
export type AdminUserCreateInput = z.infer<typeof adminUserCreateSchema>;
export type AdminUserUpdateInput = z.infer<typeof adminUserUpdateSchema>;
export type AdminUserResetInput = z.infer<typeof adminUserResetSchema>;
export type AdminPatient = z.infer<typeof adminPatientSchema>;
export type AdminClaimSummary = z.infer<typeof adminClaimSummarySchema>;
export type AdminClaimDetail = z.infer<typeof adminClaimDetailSchema>;
export type ClaimStatus = z.infer<typeof claimStatusSchema>;
