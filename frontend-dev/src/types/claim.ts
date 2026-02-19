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

export interface MLPredictionDTO {
  id: number;
  created_at: string;
  model_version: string;
  claim_id: number;
  mcp_code: string;
  insurance_company_id: number;
  prediction: string;
  confidence?: number;
  explanation?: string;
}

export interface McpPaymentPredictionDTO {
  created_at: string;
  model_version: string;
  prediction_date: string;
  insurance_company_id: number;
  mcp_code: string;
  predicted_paid_amount: number;
  confidence?: number;
}

export type ClaimFinancialFlag = {
  code: string;
  severity: "info" | "warn" | "high";
  message: string;
};

export type ClaimFinancialPrediction = {
  mcp_code: string;
  predicted_paid_amount: number;
  confidence?: number;
  explanation?: string;
  source: "ml_predictions" | "mcp_payment_predictions";
};

export interface ClaimFinancialSummaryDTO {
  claim_id: number;
  currency: "USD";
  predicted_total_paid_amount: number;
  predicted_per_mcp: ClaimFinancialPrediction[];
  flags: ClaimFinancialFlag[];
  updated_at: string;
}
