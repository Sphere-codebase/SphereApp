export interface DashboardSessionDTO {
  id: number;
  title?: string;
  updated_at: string;
}

export interface DashboardClaimDTO {
  id: number;
  patient_name: string;
  service_date?: string;
  claim_status: "draft" | "final";
  insurance_company_name?: string;
  updated_at: string;
}

export interface DoctorDashboardDTO {
  doctor: { id: number; full_name?: string };
  active_sessions: DashboardSessionDTO[];
  recent_claims: DashboardClaimDTO[];
}
