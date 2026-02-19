import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { getPatient, getPatientClaims } from "@/api/patients";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createSession } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import { queryKeys } from "@/lib/query/keys";
import type { PatientClaimListItemDTO, PatientDetailDTO } from "@/types/patients";

const CLAIMS_LIMIT = 10;

function formatDate(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString();
}

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

function formatName(patient?: PatientDetailDTO | null): string {
  if (!patient) {
    return "—";
  }
  const name = [patient.first_name, patient.last_name].filter(Boolean).join(" ");
  return name || "—";
}

export default function PatientProfilePage() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const { patientId } = useParams<{ patientId: string }>();
  const parsedPatientId = patientId ? Number(patientId) : null;

  const [claimsOffset, setClaimsOffset] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isStartingClaim, setIsStartingClaim] = useState(false);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  useEffect(() => {
    setClaimsOffset(0);
  }, [parsedPatientId]);

  const {
    data: patient,
    isLoading,
    error: patientError,
  } = useQuery<PatientDetailDTO, ApiError>({
    queryKey: parsedPatientId ? queryKeys.patient(parsedPatientId) : ["patient", "none"],
    queryFn: () => getPatient(parsedPatientId as number),
    enabled: Boolean(parsedPatientId && Number.isFinite(parsedPatientId)),
    staleTime: 60_000,
    onError: (err) => {
      if (err.status === 401 || err.status === 403) {
        handleUnauthorized();
      }
    },
  });

  const {
    data: claimsData,
    isLoading: isLoadingClaims,
    error: claimsError,
  } = useQuery<{ items: PatientClaimListItemDTO[]; total: number }, ApiError>({
    queryKey: parsedPatientId
      ? queryKeys.patientClaims(parsedPatientId, { limit: CLAIMS_LIMIT, offset: claimsOffset })
      : ["patientClaims", "none"],
    queryFn: () =>
      getPatientClaims(parsedPatientId as number, {
        limit: CLAIMS_LIMIT,
        offset: claimsOffset,
      }),
    enabled: Boolean(parsedPatientId && Number.isFinite(parsedPatientId)),
    staleTime: 30_000,
    onError: (err) => {
      if (err.status === 401 || err.status === 403) {
        handleUnauthorized();
      }
    },
  });

  const handleStartClaim = async () => {
    if (!patient) {
      return;
    }
    setIsStartingClaim(true);
    setActionError(null);
    try {
      const name = formatName(patient);
      const session = await createSession(`Claim for ${name}`);
      navigate(`/app/workspace/${session.id}?openCreateClaim=1&patientId=${patient.id}`);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setActionError("Unable to start a claim for this patient.");
    } finally {
      setIsStartingClaim(false);
    }
  };

  const claims = claimsData?.items ?? [];
  const claimsTotal = claimsData?.total ?? 0;
  const claimsPage = useMemo(() => Math.floor(claimsOffset / CLAIMS_LIMIT) + 1, [claimsOffset]);
  const claimsTotalPages = useMemo(
    () => Math.ceil(claimsTotal / CLAIMS_LIMIT),
    [claimsTotal]
  );

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              {me?.clinic_name ?? "Clinic"}
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Patient Profile
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={handleStartClaim} disabled={isStartingClaim || !patient}>
              {isStartingClaim ? "Starting..." : "Start New Claim"}
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/app/patients")}
            >
              Back to Patients
            </Button>
          </div>
        </header>

        {patientError || claimsError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            Unable to load patient profile.
          </div>
        ) : null}
        {actionError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {actionError}
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Patient Details</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-24 rounded-2xl bg-slate-100 dark:bg-slate-800" />
            ) : patient ? (
              <div className="grid gap-4 text-sm text-slate-600 dark:text-slate-300 sm:grid-cols-2">
                <div>
                  <div className="text-xs uppercase text-slate-400">Name</div>
                  <div className="text-base font-semibold text-slate-900 dark:text-white">
                    {formatName(patient)}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase text-slate-400">DOB</div>
                  <div>{formatDate(patient.date_of_birth)}</div>
                </div>
                <div>
                  <div className="text-xs uppercase text-slate-400">Gender</div>
                  <div>{patient.gender ?? "—"}</div>
                </div>
                <div>
                  <div className="text-xs uppercase text-slate-400">Chart #</div>
                  <div>{patient.chart_number ?? "—"}</div>
                </div>
                <div>
                  <div className="text-xs uppercase text-slate-400">Primary Phone</div>
                  <div>{patient.primary_phone ?? "—"}</div>
                </div>
                <div>
                  <div className="text-xs uppercase text-slate-400">Secondary Phone</div>
                  <div>{patient.secondary_phone ?? "—"}</div>
                </div>
                <div className="sm:col-span-2">
                  <div className="text-xs uppercase text-slate-400">Address</div>
                  <div>
                    {patient.address
                      ? [
                          patient.address.line1,
                          patient.address.line2,
                          patient.address.city,
                          patient.address.state,
                          patient.address.zip,
                          patient.address.country,
                        ]
                          .filter(Boolean)
                          .join(", ")
                      : "—"}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-slate-500">Patient not found.</div>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Recent Claims</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {isLoadingClaims ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div
                    key={`claim-skeleton-${index}`}
                    className="h-12 rounded-2xl bg-slate-100 dark:bg-slate-800"
                  />
                ))}
              </div>
            ) : claims.length === 0 ? (
              <div className="text-sm text-slate-500">No claims yet.</div>
            ) : (
              claims.map((claim) => (
                <div
                  key={claim.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                >
                  <div className="flex flex-col gap-1">
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      Claim #{claim.id}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      Service date: {formatDate(claim.service_date)}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      Insurance: {claim.insurance_company_name ?? "—"}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      Updated: {formatDateTime(claim.updated_at)}
                    </div>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      claim.claim_status === "final"
                        ? "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
                        : "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200"
                    }`}
                  >
                    {claim.claim_status === "final" ? "Final" : "Draft"}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
          <div>
            Showing {claims.length} of {claimsTotal} claims
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setClaimsOffset((prev) => Math.max(0, prev - CLAIMS_LIMIT))}
              disabled={claimsOffset === 0 || isLoadingClaims}
            >
              Previous
            </Button>
            <span>
              Page {claimsPage} of {claimsTotalPages || 1}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setClaimsOffset((prev) => prev + CLAIMS_LIMIT)}
              disabled={claimsOffset + CLAIMS_LIMIT >= claimsTotal || isLoadingClaims}
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
