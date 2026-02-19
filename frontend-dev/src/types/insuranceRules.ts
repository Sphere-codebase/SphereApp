export type InsuranceCompanyDTO = {
  id: number;
  name: string;
};

export type PolicyLinkDTO = {
  id: number;
  insurance_company_id: number;
  mcp_code: string;
  policy_url: string;
};

export type PolicyRulesDTO = {
  policy_link_id: number;
  extracted_at?: string | null;
  rules_json?: unknown | null;
};

export type ClinicOverrideDTO = {
  policy_link_id: number;
  clinic_id: number;
  override_json?: Record<string, unknown> | null;
  updated_at?: string | null;
};

export type DoctorOverrideDTO = {
  policy_link_id: number;
  doctor_id: number;
  override_json?: Record<string, unknown> | null;
  updated_at?: string | null;
};
