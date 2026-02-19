export type ClaimDraftPreview = {
  patient?: {
    first_name?: string;
    last_name?: string;
    date_of_birth?: string;
  };
  insurance_company_id?: string;
  service_date?: string;
};
