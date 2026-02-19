import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { listPatients } from "@/api/patients";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createSession } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import type { PatientListItemDTO } from "@/types/patients";

const PAGE_LIMIT = 25;

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

function formatName(patient: PatientListItemDTO): string {
  const name = [patient.first_name, patient.last_name].filter(Boolean).join(" ");
  return name || "—";
}

export default function PatientsListPage() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [patients, setPatients] = useState<PatientListItemDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingPatientId, setCreatingPatientId] = useState<number | null>(null);
  const [isCreatingGlobal, setIsCreatingGlobal] = useState(false);

  const totalPages = useMemo(() => Math.ceil(total / PAGE_LIMIT), [total]);
  const currentPage = useMemo(() => Math.floor(offset / PAGE_LIMIT) + 1, [offset]);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const loadPatients = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listPatients({ query, limit: PAGE_LIMIT, offset });
      setPatients(response.items);
      setTotal(response.total);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load patients.");
    } finally {
      setIsLoading(false);
    }
  }, [query, offset, handleUnauthorized]);

  useEffect(() => {
    void loadPatients();
  }, [loadPatients]);

  const handleSearchSubmit = (event: FormEvent) => {
    event.preventDefault();
    setOffset(0);
    setQuery(searchInput.trim());
  };

  const handleStartClaim = async (patient: PatientListItemDTO) => {
    setCreatingPatientId(patient.id);
    setError(null);
    try {
      const name = formatName(patient);
      const session = await createSession(`Claim for ${name}`);
      navigate(`/app/workspace/${session.id}?openCreateClaim=1&patientId=${patient.id}`);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to start a claim for this patient.");
    } finally {
      setCreatingPatientId(null);
    }
  };

  const handleStartNewClaim = async () => {
    setIsCreatingGlobal(true);
    setError(null);
    try {
      const session = await createSession("New claim");
      navigate(`/app/workspace/${session.id}?openCreateClaim=1`);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to start a new claim.");
    } finally {
      setIsCreatingGlobal(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              {me?.clinic_name ?? "Clinic"}
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Patients
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={handleStartNewClaim} disabled={isCreatingGlobal}>
              {isCreatingGlobal ? "Starting..." : "Start New Claim"}
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/app/dashboard")}
            >
              Dashboard
            </Button>
          </div>
        </header>

        <form
          onSubmit={handleSearchSubmit}
          className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"
        >
          <input
            type="text"
            placeholder="Search by name or chart #"
            className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Patient List</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div
                    key={`patient-skeleton-${index}`}
                    className="h-14 rounded-2xl bg-slate-100 dark:bg-slate-800"
                  />
                ))}
              </div>
            ) : patients.length === 0 ? (
              <div className="text-sm text-slate-500">No patients found.</div>
            ) : (
              patients.map((patient) => (
                <div
                  key={patient.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                >
                  <div className="flex flex-1 flex-col gap-1">
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      {formatName(patient)}
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <span>DOB: {formatDate(patient.date_of_birth)}</span>
                      <span>Chart: {patient.chart_number ?? "—"}</span>
                      <span>Phone: {patient.primary_phone ?? "—"}</span>
                      {patient.doctor_name ? (
                        <span>Doctor: {patient.doctor_name}</span>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => navigate(`/app/patients/${patient.id}`)}
                    >
                      Open
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void handleStartClaim(patient)}
                      disabled={creatingPatientId === patient.id}
                    >
                      {creatingPatientId === patient.id ? "Starting..." : "Start Claim"}
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
          <div>
            Showing {patients.length} of {total} patients
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_LIMIT))}
              disabled={offset === 0 || isLoading}
            >
              Previous
            </Button>
            <span>
              Page {currentPage} of {totalPages || 1}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setOffset((prev) => prev + PAGE_LIMIT)}
              disabled={offset + PAGE_LIMIT >= total || isLoading}
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
