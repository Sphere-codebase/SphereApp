export type DoctorUserDTO = {
  id: number;
  email: string;
  full_name?: string | null;
  role: "doctor" | "chief_doctor" | "clinic_admin" | "platform_staff_admin";
  is_active: boolean;
  created_at?: string | null;
};

export type AuditLogItemDTO = {
  id: number;
  created_at?: string | null;
  actor_id?: number | null;
  actor_name?: string | null;
  actor_role?: string | null;
  action: string;
  entity: string;
  entity_id?: string | null;
  diff_json?: Record<string, unknown> | null;
  request_id?: string | null;
};

export type ClinicDashboardDTO = {
  range: { from: string; to: string };
  kpis: {
    total_claims: number;
    draft_claims: number;
    finalized_claims: number;
    active_doctors: number;
  };
  top_insurers: Array<{ insurance_company_id: number; name: string; claim_count: number }>;
  claims_timeseries: Array<{ date: string; count: number }>;
  ai_timeseries: Array<{ date: string; count: number }>;
  recent_activity: AuditLogItemDTO[];
};

export type ClinicAuditLogResponseDTO = {
  items: AuditLogItemDTO[];
  limit: number;
  offset: number;
  total: number;
};

export type ClinicDoctorsResponseDTO = {
  items: DoctorUserDTO[];
};
