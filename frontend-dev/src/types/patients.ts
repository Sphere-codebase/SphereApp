export type PatientListItemDTO = {
  id: number;
  first_name?: string | null;
  last_name?: string | null;
  date_of_birth?: string | null;
  chart_number?: string | null;
  primary_phone?: string | null;
  doctor_id?: number | null;
  doctor_name?: string | null;
};

export type PatientListResponseDTO = {
  items: PatientListItemDTO[];
  limit: number;
  offset: number;
  total: number;
};

export type PatientAddressDTO = {
  line1: string;
  line2?: string | null;
  city: string;
  state?: string | null;
  zip?: string | null;
  country?: string | null;
};

export type PatientDetailDTO = {
  id: number;
  first_name?: string | null;
  last_name?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  chart_number?: string | null;
  primary_phone?: string | null;
  secondary_phone?: string | null;
  address?: PatientAddressDTO | null;
  doctor_id?: number | null;
};

export type PatientClaimListItemDTO = {
  id: number;
  service_date?: string | null;
  claim_status: "draft" | "final";
  insurance_company_name?: string | null;
  updated_at?: string | null;
};

export type PatientClaimsResponseDTO = {
  items: PatientClaimListItemDTO[];
  limit: number;
  offset: number;
  total: number;
};
