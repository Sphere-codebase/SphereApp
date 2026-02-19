export interface PatientDTO {
  id?: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string;
}

export interface MCPCodeDTO {
  code: string;
  description: string;
}

export interface DiagnosisCodeDTO {
  code: string;
  description: string;
}

export interface ClaimDTO {
  id: number;
  claim_status: "draft" | "final";
  patient: PatientDTO;
  insurance_company_id: number;
  service_date: string;
  mcp_codes: MCPCodeDTO[];
  diagnosis_codes: DiagnosisCodeDTO[];
}
