import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { searchMcpCodes } from "@/api/claims";
import {
  deleteClinicOverride,
  deleteDoctorOverride,
  getClinicOverride,
  getDoctorOverride,
  getPolicyRules,
  listInsuranceCompanies,
  listPolicyLinks,
  upsertClinicOverride,
  upsertDoctorOverride,
} from "@/api/insuranceRules";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import type { MCPCodeDTO } from "@/types/claim";
import type {
  ClinicOverrideDTO,
  DoctorOverrideDTO,
  InsuranceCompanyDTO,
  PolicyLinkDTO,
  PolicyRulesDTO,
} from "@/types/insuranceRules";

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function deepMerge(
  base: Record<string, unknown>,
  override: Record<string, unknown>
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...base };
  Object.entries(override).forEach(([key, value]) => {
    if (isPlainObject(value) && isPlainObject(result[key])) {
      result[key] = deepMerge(result[key] as Record<string, unknown>, value);
    } else {
      result[key] = value;
    }
  });
  return result;
}

function toJsonText(value: unknown): string {
  if (!value || (isPlainObject(value) && Object.keys(value).length === 0)) {
    return "{}";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "{}";
  }
}

function parseJsonObject(text: string): {
  value: Record<string, unknown> | null;
  error: string | null;
} {
  if (!text.trim()) {
    return { value: {}, error: null };
  }
  try {
    const parsed = JSON.parse(text);
    if (!isPlainObject(parsed)) {
      return { value: null, error: "Override must be a JSON object." };
    }
    return { value: parsed, error: null };
  } catch {
    return { value: null, error: "Invalid JSON." };
  }
}

export default function InsuranceRulesPage() {
  const { me, logout, hasRole } = useAuth();
  const navigate = useNavigate();

  const [insuranceQuery, setInsuranceQuery] = useState("");
  const [insuranceOptions, setInsuranceOptions] = useState<InsuranceCompanyDTO[]>([]);
  const [selectedInsurance, setSelectedInsurance] = useState<InsuranceCompanyDTO | null>(
    null
  );
  const [isLoadingCompanies, setIsLoadingCompanies] = useState(false);

  const [mcpQuery, setMcpQuery] = useState("");
  const [mcpOptions, setMcpOptions] = useState<MCPCodeDTO[]>([]);
  const [selectedMcp, setSelectedMcp] = useState<MCPCodeDTO | null>(null);
  const [isLoadingMcp, setIsLoadingMcp] = useState(false);

  const [policyLinks, setPolicyLinks] = useState<PolicyLinkDTO[]>([]);
  const [selectedPolicyLinkId, setSelectedPolicyLinkId] = useState<number | null>(null);
  const [isLoadingPolicyLinks, setIsLoadingPolicyLinks] = useState(false);

  const [baseRules, setBaseRules] = useState<PolicyRulesDTO | null>(null);
  const [clinicOverride, setClinicOverride] = useState<ClinicOverrideDTO | null>(null);
  const [doctorOverride, setDoctorOverride] = useState<DoctorOverrideDTO | null>(null);

  const [clinicDraft, setClinicDraft] = useState("{}");
  const [doctorDraft, setDoctorDraft] = useState("{}");
  const [clinicDraftError, setClinicDraftError] = useState<string | null>(null);
  const [doctorDraftError, setDoctorDraftError] = useState<string | null>(null);

  const [isLoadingRules, setIsLoadingRules] = useState(false);
  const [isSavingClinicOverride, setIsSavingClinicOverride] = useState(false);
  const [isSavingDoctorOverride, setIsSavingDoctorOverride] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canEditClinic = hasRole("chief_doctor") || hasRole("clinic_admin");
  const canEditDoctor = hasRole("doctor") || hasRole("chief_doctor") || hasRole("clinic_admin");

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  useEffect(() => {
    if (!insuranceQuery.trim()) {
      setInsuranceOptions([]);
      return;
    }
    setIsLoadingCompanies(true);
    const handle = window.setTimeout(() => {
      listInsuranceCompanies(insuranceQuery.trim())
        .then((items) => setInsuranceOptions(items))
        .catch((err) => {
          if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
            handleUnauthorized();
            return;
          }
          setInsuranceOptions([]);
        })
        .finally(() => setIsLoadingCompanies(false));
    }, 300);
    return () => window.clearTimeout(handle);
  }, [insuranceQuery, handleUnauthorized]);

  useEffect(() => {
    setPolicyLinks([]);
    setSelectedPolicyLinkId(null);
  }, [selectedInsurance?.id, selectedMcp?.code]);

  useEffect(() => {
    if (!mcpQuery.trim()) {
      setMcpOptions([]);
      return;
    }
    setIsLoadingMcp(true);
    const handle = window.setTimeout(() => {
      searchMcpCodes(mcpQuery.trim())
        .then((items) => setMcpOptions(items))
        .catch((err) => {
          if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
            handleUnauthorized();
            return;
          }
          setMcpOptions([]);
        })
        .finally(() => setIsLoadingMcp(false));
    }, 300);
    return () => window.clearTimeout(handle);
  }, [mcpQuery, handleUnauthorized]);

  const handleLoadPolicyLinks = async () => {
    if (!selectedInsurance || !selectedMcp) {
      setError("Select an insurance company and MCP code.");
      return;
    }
    setError(null);
    setIsLoadingPolicyLinks(true);
    try {
      const items = await listPolicyLinks({
        insurance_company_id: selectedInsurance.id,
        mcp_code: selectedMcp.code,
      });
      setPolicyLinks(items);
      setSelectedPolicyLinkId(items[0]?.id ?? null);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load policy links.");
      setPolicyLinks([]);
      setSelectedPolicyLinkId(null);
    } finally {
      setIsLoadingPolicyLinks(false);
    }
  };

  useEffect(() => {
    if (!selectedPolicyLinkId) {
      setBaseRules(null);
      setClinicOverride(null);
      setDoctorOverride(null);
      setClinicDraft("{}");
      setDoctorDraft("{}");
      return;
    }
    setIsLoadingRules(true);
    setError(null);
    Promise.all([
      getPolicyRules(selectedPolicyLinkId),
      getClinicOverride(selectedPolicyLinkId),
      getDoctorOverride(selectedPolicyLinkId),
    ])
      .then(([rules, clinic, doctor]) => {
        setBaseRules(rules);
        setClinicOverride(clinic);
        setDoctorOverride(doctor);
        setClinicDraft(toJsonText(clinic.override_json));
        setDoctorDraft(toJsonText(doctor.override_json));
      })
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          handleUnauthorized();
          return;
        }
        setError("Unable to load policy rules.");
      })
      .finally(() => setIsLoadingRules(false));
  }, [selectedPolicyLinkId, handleUnauthorized]);

  const handleClinicDraftChange = (value: string) => {
    setClinicDraft(value);
    const parsed = parseJsonObject(value);
    setClinicDraftError(parsed.error);
  };

  const handleDoctorDraftChange = (value: string) => {
    setDoctorDraft(value);
    const parsed = parseJsonObject(value);
    setDoctorDraftError(parsed.error);
  };

  const handleSaveClinicOverride = async () => {
    if (!selectedPolicyLinkId) {
      return;
    }
    const parsed = parseJsonObject(clinicDraft);
    if (parsed.error || !parsed.value) {
      setClinicDraftError(parsed.error ?? "Invalid JSON.");
      return;
    }
    setIsSavingClinicOverride(true);
    setError(null);
    try {
      const updated = await upsertClinicOverride(selectedPolicyLinkId, parsed.value);
      setClinicOverride(updated);
      setClinicDraft(toJsonText(updated.override_json));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to save clinic override.");
    } finally {
      setIsSavingClinicOverride(false);
    }
  };

  const handleSaveDoctorOverride = async () => {
    if (!selectedPolicyLinkId) {
      return;
    }
    const parsed = parseJsonObject(doctorDraft);
    if (parsed.error || !parsed.value) {
      setDoctorDraftError(parsed.error ?? "Invalid JSON.");
      return;
    }
    setIsSavingDoctorOverride(true);
    setError(null);
    try {
      const updated = await upsertDoctorOverride(selectedPolicyLinkId, parsed.value);
      setDoctorOverride(updated);
      setDoctorDraft(toJsonText(updated.override_json));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to save doctor override.");
    } finally {
      setIsSavingDoctorOverride(false);
    }
  };

  const handleResetClinicOverride = async () => {
    if (!selectedPolicyLinkId) {
      return;
    }
    setIsSavingClinicOverride(true);
    setError(null);
    try {
      await deleteClinicOverride(selectedPolicyLinkId);
      setClinicOverride(null);
      setClinicDraft("{}");
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to clear clinic override.");
    } finally {
      setIsSavingClinicOverride(false);
    }
  };

  const handleResetDoctorOverride = async () => {
    if (!selectedPolicyLinkId) {
      return;
    }
    setIsSavingDoctorOverride(true);
    setError(null);
    try {
      await deleteDoctorOverride(selectedPolicyLinkId);
      setDoctorOverride(null);
      setDoctorDraft("{}");
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to clear doctor override.");
    } finally {
      setIsSavingDoctorOverride(false);
    }
  };

  const selectedPolicyLink = useMemo(
    () => policyLinks.find((link) => link.id === selectedPolicyLinkId) ?? null,
    [policyLinks, selectedPolicyLinkId]
  );

  const effectiveRules = useMemo(() => {
    const base = isPlainObject(baseRules?.rules_json) ? (baseRules?.rules_json as Record<string, unknown>) : {};
    const clinic = isPlainObject(clinicOverride?.override_json) ? (clinicOverride?.override_json as Record<string, unknown>) : {};
    const doctor = isPlainObject(doctorOverride?.override_json) ? (doctorOverride?.override_json as Record<string, unknown>) : {};
    return deepMerge(deepMerge(base, clinic), doctor);
  }, [baseRules, clinicOverride, doctorOverride]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              {me?.clinic_name ?? "Clinic"}
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Insurance Rules
            </h1>
          </div>
          <Button type="button" variant="outline" onClick={() => navigate("/app/dashboard")}>
            Dashboard
          </Button>
        </header>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Selector</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase text-slate-500">Insurance Company</label>
              <input
                type="text"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                placeholder="Search insurance company"
                value={insuranceQuery}
                onChange={(event) => {
                  setInsuranceQuery(event.target.value);
                  setSelectedInsurance(null);
                }}
              />
              <div className="rounded-xl border border-slate-200 bg-white text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
                {isLoadingCompanies ? (
                  <div className="px-3 py-2">Searching...</div>
                ) : insuranceOptions.length === 0 ? (
                  <div className="px-3 py-2">No matches.</div>
                ) : (
                  insuranceOptions.map((company) => (
                    <button
                      key={company.id}
                      type="button"
                      className={`block w-full px-3 py-2 text-left transition hover:bg-slate-100 dark:hover:bg-slate-800 ${
                        selectedInsurance?.id === company.id ? "bg-slate-100 dark:bg-slate-800" : ""
                      }`}
                      onClick={() => {
                        setSelectedInsurance(company);
                        setInsuranceQuery(company.name);
                      }}
                    >
                      {company.name}
                    </button>
                  ))
                )}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase text-slate-500">MCP Code</label>
              <input
                type="text"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                placeholder="Search MCP code"
                value={mcpQuery}
                onChange={(event) => {
                  setMcpQuery(event.target.value);
                  setSelectedMcp(null);
                }}
              />
              <div className="rounded-xl border border-slate-200 bg-white text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
                {isLoadingMcp ? (
                  <div className="px-3 py-2">Searching...</div>
                ) : mcpOptions.length === 0 ? (
                  <div className="px-3 py-2">No matches.</div>
                ) : (
                  mcpOptions.map((code) => (
                    <button
                      key={code.code}
                      type="button"
                      className={`block w-full px-3 py-2 text-left transition hover:bg-slate-100 dark:hover:bg-slate-800 ${
                        selectedMcp?.code === code.code ? "bg-slate-100 dark:bg-slate-800" : ""
                      }`}
                      onClick={() => {
                        setSelectedMcp(code);
                        setMcpQuery(code.code);
                      }}
                    >
                      {code.code} — {code.description || "No description"}
                    </button>
                  ))
                )}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase text-slate-500">Policy Links</label>
              <select
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={selectedPolicyLinkId ?? ""}
                onChange={(event) => {
                  const value = event.target.value;
                  setSelectedPolicyLinkId(value ? Number(value) : null);
                }}
                disabled={policyLinks.length === 0}
              >
                <option value="">Select a policy link</option>
                {policyLinks.map((link) => (
                  <option key={link.id} value={link.id}>
                    {link.policy_url}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                onClick={handleLoadPolicyLinks}
                disabled={!selectedInsurance || !selectedMcp || isLoadingPolicyLinks}
              >
                {isLoadingPolicyLinks ? "Loading..." : "Load Rules"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {selectedPolicyLink ? (
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
            <div>Policy Link ID: {selectedPolicyLink.id}</div>
            <div>Policy URL: {selectedPolicyLink.policy_url}</div>
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Base Policy Rules (Latest Extract)</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingRules ? (
              <div className="h-32 rounded-2xl bg-slate-100 dark:bg-slate-800" />
            ) : baseRules?.rules_json ? (
              <div className="space-y-2">
                <div className="text-xs text-slate-500">
                  Extracted: {formatDateTime(baseRules.extracted_at)}
                </div>
                <pre className="max-h-72 overflow-auto rounded-2xl bg-slate-50 p-3 text-xs text-slate-700 dark:bg-slate-950 dark:text-slate-200">
                  {JSON.stringify(baseRules.rules_json, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="text-sm text-slate-500">No extracted rules for this policy link.</div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Clinic Override</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-xs text-slate-500">
                Updated: {formatDateTime(clinicOverride?.updated_at)}
              </div>
              <textarea
                className="h-56 w-full rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={clinicDraft}
                onChange={(event) => handleClinicDraftChange(event.target.value)}
                disabled={!canEditClinic || !selectedPolicyLinkId}
              />
              {clinicDraftError ? (
                <div className="text-xs text-rose-600">{clinicDraftError}</div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  onClick={handleSaveClinicOverride}
                  disabled={!canEditClinic || isSavingClinicOverride || !selectedPolicyLinkId}
                >
                  {isSavingClinicOverride ? "Saving..." : "Save Clinic Override"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleResetClinicOverride}
                  disabled={!canEditClinic || isSavingClinicOverride || !selectedPolicyLinkId}
                >
                  Reset
                </Button>
              </div>
              {!canEditClinic ? (
                <div className="text-xs text-slate-500">
                  Clinic overrides are editable by chief doctor or clinic admin.
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Doctor Override</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-xs text-slate-500">
                Updated: {formatDateTime(doctorOverride?.updated_at)}
              </div>
              <textarea
                className="h-56 w-full rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={doctorDraft}
                onChange={(event) => handleDoctorDraftChange(event.target.value)}
                disabled={!canEditDoctor || !selectedPolicyLinkId}
              />
              {doctorDraftError ? (
                <div className="text-xs text-rose-600">{doctorDraftError}</div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  onClick={handleSaveDoctorOverride}
                  disabled={!canEditDoctor || isSavingDoctorOverride || !selectedPolicyLinkId}
                >
                  {isSavingDoctorOverride ? "Saving..." : "Save Doctor Override"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleResetDoctorOverride}
                  disabled={!canEditDoctor || isSavingDoctorOverride || !selectedPolicyLinkId}
                >
                  Reset
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Effective Rules Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-72 overflow-auto rounded-2xl bg-slate-50 p-3 text-xs text-slate-700 dark:bg-slate-950 dark:text-slate-200">
              {JSON.stringify(effectiveRules, null, 2)}
            </pre>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
