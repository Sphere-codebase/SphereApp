export const queryKeys = {
  me: ["me"] as const,
  dashboard: ["dashboard"] as const,
  patients: (filters: Record<string, unknown>) => ["patients", filters] as const,
  patient: (id: number) => ["patient", id] as const,
  patientClaims: (id: number, filters: Record<string, unknown>) =>
    ["patientClaims", id, filters] as const,
  claim: (id: number) => ["claim", id] as const,
  claimFinancial: (id: number) => ["claimFinancial", id] as const,
  auditLogs: (scope: "clinic" | "platform", filters: Record<string, unknown>) =>
    ["auditLogs", scope, filters] as const,
  clinicDoctors: ["clinicDoctors"] as const,
  platformClinics: (scope: string) => ["platformClinics", scope] as const,
  policyLinks: (companyId: number | null, mcpCode: string | null) =>
    ["policyLinks", companyId, mcpCode] as const,
  policyRules: (policyLinkId: number | null) => ["policyRules", policyLinkId] as const,
  overrides: (policyLinkId: number | null) => ["overrides", policyLinkId] as const,
  sessions: (filters: Record<string, unknown>) => ["sessions", filters] as const,
  sessionMessages: (sessionId: number | null) => ["sessionMessages", sessionId] as const,
};
