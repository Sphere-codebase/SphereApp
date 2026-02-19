import { z } from "zod";

const dateString = z.string();

export const insuranceCompanySchema = z.object({
  id: z.number(),
  name: z.string(),
  created_at: dateString.nullable(),
});

export const insuranceCompanyCreateSchema = z.object({
  name: z.string(),
});

export const insuranceCompanyUpdateSchema = insuranceCompanyCreateSchema.partial();

export const mcpCodeSchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

export const mcpCodeCreateSchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

export const mcpCodeUpdateSchema = z.object({
  description: z.string().nullable().optional(),
});

export const diagnosisCodeSchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

export const diagnosisCodeCreateSchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

export const diagnosisCodeUpdateSchema = z.object({
  description: z.string().nullable().optional(),
});

export const policyLinkSchema = z.object({
  id: z.number(),
  insurance_company_id: z.number(),
  mcp_code: z.string(),
  policy_url: z.string().url(),
  created_at: dateString.nullable(),
});

export const policyLinkCreateSchema = z.object({
  insurance_company_id: z.number(),
  mcp_code: z.string(),
  policy_url: z.string(),
});

export const policyLinkUpdateSchema = policyLinkCreateSchema.partial();

export const policyRulesParseProposedSchema = z.object({
  title: z.string().nullable(),
  next_review_iso: z.string().nullable(),
  criteria_count: z.number(),
  notes_count: z.number(),
  medical_necessity_clean_preview: z.string(),
});

export const policyRulesParseActionSchema = z.object({
  action_required: z.literal(true),
  proposed_changes: policyRulesParseProposedSchema,
  next_action: z.any().optional(),
});

export const policyRulesParseStoredSchema = z.object({
  status: z.literal("stored"),
  policy_link_id: z.number(),
  policy_rules_id: z.number(),
  title: z.string().nullable(),
  next_review_iso: z.string().nullable(),
  criteria_count: z.number(),
  notes_count: z.number(),
});

export const policyRulesParseResponseSchema = z.union([
  policyRulesParseActionSchema,
  policyRulesParseStoredSchema,
]);

export const policyRuleSchema = z.object({
  policy_rules_id: z.number(),
  policy_link_id: z.number(),
  extracted_at: dateString,
  title: z.string().nullable(),
  next_review_iso: z.string().nullable(),
  criteria_json: z.any().nullable(),
  notes_json: z.any().nullable(),
  medical_necessity_clean: z.string().nullable(),
});

export const adminUserSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  full_name: z.string().nullable(),
  is_active: z.boolean(),
  roles: z.array(z.string()),
  created_at: dateString.nullable(),
});

export const adminUserCreateSchema = z.object({
  email: z.string().email(),
  full_name: z.string().nullable().optional(),
  password: z.string(),
  roles: z.array(z.string()).optional(),
  is_active: z.boolean(),
});

export const adminUserUpdateSchema = z.object({
  email: z.string().email().nullable().optional(),
  full_name: z.string().nullable().optional(),
  roles: z.array(z.string()).optional(),
  is_active: z.boolean().optional(),
});

export const adminUserResetSchema = z.object({
  password: z.string(),
});

export const adminPatientSchema = z.object({
  id: z.number(),
  doctor_id: z.number(),
  first_name: z.string().nullable(),
  last_name: z.string().nullable(),
  date_of_birth: z.string().nullable(),
  created_at: dateString.nullable(),
});

export const claimStatusSchema = z.enum([
  "DRAFT",
  "SUBMITTED",
  "PAID",
  "DENIED",
  "FINAL",
]);
const claimStatusNullableSchema = claimStatusSchema.nullable();

export const adminClaimSummarySchema = z.object({
  id: z.number(),
  patient_id: z.number(),
  patient_name: z.string(),
  doctor_id: z.number(),
  insurance_company_id: z.number(),
  insurance_company_name: z.string().nullable(),
  claim_number: z.string().nullable(),
  claim_status: claimStatusNullableSchema,
  service_date: z.string().nullable(),
  claim_date: z.string().nullable(),
  billed_amount_total: z.number().nullable(),
  allowed_amount_total: z.number().nullable(),
  coinsurance_amount_total: z.number().nullable(),
  copay_amount_total: z.number().nullable(),
  deductible_amount_total: z.number().nullable(),
  created_at: dateString.nullable(),
});

export const mcpCodeSummarySchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

export const adminClaimProcedureFactSchema = z.object({
  id: z.number(),
  mcp_code: mcpCodeSummarySchema,
  service_date: z.string().nullable(),
  units: z.number().nullable(),
  modifier: z.string().nullable(),
  billed_amount: z.number().nullable(),
  allowed_amount: z.number().nullable(),
  coinsurance_amount: z.number().nullable(),
  copay_amount: z.number().nullable(),
  deductible_amount: z.number().nullable(),
  paid_amount: z.number().nullable(),
  paid_at: z.string().nullable(),
  created_at: dateString.nullable(),
});

export const diagnosisCodeSummarySchema = z.object({
  code: z.string(),
  description: z.string().nullable().optional(),
});

export const adminClaimDetailSchema = z.object({
  id: z.number(),
  patient: adminPatientSchema,
  insurance_company: insuranceCompanySchema.nullable(),
  claim_number: z.string().nullable(),
  claim_status: claimStatusNullableSchema,
  service_date: z.string().nullable(),
  claim_date: z.string().nullable(),
  billed_amount_total: z.number().nullable(),
  allowed_amount_total: z.number().nullable(),
  coinsurance_amount_total: z.number().nullable(),
  copay_amount_total: z.number().nullable(),
  deductible_amount_total: z.number().nullable(),
  created_at: dateString.nullable(),
  procedures: z.array(adminClaimProcedureFactSchema),
  diagnoses: z.array(diagnosisCodeSummarySchema),
});

export type InsuranceCompany = z.infer<typeof insuranceCompanySchema>;
export type InsuranceCompanyCreateInput = z.infer<typeof insuranceCompanyCreateSchema>;
export type InsuranceCompanyUpdateInput = z.infer<typeof insuranceCompanyUpdateSchema>;
export type McpCode = z.infer<typeof mcpCodeSchema>;
export type McpCodeCreateInput = z.infer<typeof mcpCodeCreateSchema>;
export type McpCodeUpdateInput = z.infer<typeof mcpCodeUpdateSchema>;
export type DiagnosisCode = z.infer<typeof diagnosisCodeSchema>;
export type DiagnosisCodeCreateInput = z.infer<typeof diagnosisCodeCreateSchema>;
export type DiagnosisCodeUpdateInput = z.infer<typeof diagnosisCodeUpdateSchema>;
export type PolicyLink = z.infer<typeof policyLinkSchema>;
export type PolicyLinkCreateInput = z.infer<typeof policyLinkCreateSchema>;
export type PolicyLinkUpdateInput = z.infer<typeof policyLinkUpdateSchema>;
export type PolicyRulesParseProposed = z.infer<typeof policyRulesParseProposedSchema>;
export type PolicyRulesParseResponse = z.infer<typeof policyRulesParseResponseSchema>;
export type PolicyRule = z.infer<typeof policyRuleSchema>;
export type AdminUser = z.infer<typeof adminUserSchema>;
export type AdminUserCreateInput = z.infer<typeof adminUserCreateSchema>;
export type AdminUserUpdateInput = z.infer<typeof adminUserUpdateSchema>;
export type AdminUserResetInput = z.infer<typeof adminUserResetSchema>;
export type AdminPatient = z.infer<typeof adminPatientSchema>;
export type AdminClaimSummary = z.infer<typeof adminClaimSummarySchema>;
export type AdminClaimDetail = z.infer<typeof adminClaimDetailSchema>;
export type ClaimStatus = z.infer<typeof claimStatusSchema>;
