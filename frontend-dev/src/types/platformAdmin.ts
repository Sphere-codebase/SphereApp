export type PlatformClinicDTO = {
  id: number;
  name: string;
  phone?: string | null;
  billing_provider_npi?: string | null;
  billing_provider_tax_id?: string | null;
  billing_provider_organization_name?: string | null;
  is_blocked?: boolean | null;
  created_at?: string | null;
  counters?: {
    doctors_count?: number | null;
    patients_count?: number | null;
    claims_30d?: number | null;
  } | null;
};

export type PlatformClinicsResponseDTO = {
  items: PlatformClinicDTO[];
  limit: number;
  offset: number;
  total: number;
};

export type PlatformAuditItemDTO = {
  id: number;
  created_at?: string | null;
  clinic_id: number;
  clinic_name?: string | null;
  actor_id?: number | null;
  actor_name?: string | null;
  actor_role?: string | null;
  action: string;
  entity: string;
  entity_id?: string | null;
  diff_json?: Record<string, unknown> | null;
  request_id?: string | null;
};

export type PlatformAuditResponseDTO = {
  items: PlatformAuditItemDTO[];
  limit: number;
  offset: number;
  total: number;
};

export type PlatformUsageDTO = {
  range: { from: string; to: string };
  scope: { clinic_id?: number | null };
  kpis: {
    claims_created: number;
    claims_finalized: number;
    pdf_generated: number;
    ai_actions: number;
    active_clinics: number;
  };
  timeseries: {
    claims: Array<{ date: string; count: number }>;
    pdf: Array<{ date: string; count: number }>;
    ai: Array<{ date: string; count: number }>;
  };
  top_clinics: Array<{ clinic_id: number; clinic_name: string; claims: number; pdf: number; ai: number }>;
};
