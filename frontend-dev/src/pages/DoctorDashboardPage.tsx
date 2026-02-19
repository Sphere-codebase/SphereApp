import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDoctorDashboard } from "@/api/dashboard";
import { createSession } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { DoctorDashboardDTO } from "@/types/dashboard";

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleDateString();
}

export default function DoctorDashboardPage() {
  const navigate = useNavigate();
  const { me, logout } = useAuth();
  const [dashboard, setDashboard] = useState<DoctorDashboardDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getDoctorDashboard();
      setDashboard(data);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const handleStartNewClaim = async () => {
    setIsCreating(true);
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
      setIsCreating(false);
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
              Dashboard
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={handleStartNewClaim} disabled={isCreating}>
              {isCreating ? "Starting..." : "Start New Claim"}
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/app/workspace")}>
              Workspace
            </Button>
          </div>
        </header>

        <nav className="flex flex-wrap gap-2 text-sm">
          <Button type="button" variant="secondary" disabled>
            Dashboard
          </Button>
          <Button type="button" variant="ghost" onClick={() => navigate("/app/workspace")}>
            Workspace
          </Button>
          <Button type="button" variant="ghost" onClick={() => navigate("/app/patients")}>
            Patients
          </Button>
          <Button type="button" variant="ghost" onClick={() => navigate("/app/insurance-rules")}>
            Insurance Rules
          </Button>
          <Button type="button" variant="ghost" onClick={() => navigate("/app/ai-history")}>
            AI History
          </Button>
        </nav>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>{error}</span>
              <Button type="button" size="sm" variant="outline" onClick={loadDashboard}>
                Retry
              </Button>
            </div>
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Active Chats</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, index) => (
                    <div
                      key={`session-skeleton-${index}`}
                      className="h-16 rounded-2xl bg-slate-100 dark:bg-slate-800"
                    />
                  ))}
                </div>
              ) : dashboard?.active_sessions.length ? (
                dashboard.active_sessions.map((session) => (
                  <button
                    key={session.id}
                    type="button"
                    onClick={() => navigate(`/app/workspace/${session.id}`)}
                    className="flex w-full flex-col gap-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
                  >
                    <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {session.title || `Session ${session.id}`}
                    </span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      Updated {formatDateTime(session.updated_at)}
                    </span>
                  </button>
                ))
              ) : (
                <div className="text-sm text-slate-500">No active sessions yet.</div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Recent Claims</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, index) => (
                    <div
                      key={`claim-skeleton-${index}`}
                      className="h-16 rounded-2xl bg-slate-100 dark:bg-slate-800"
                    />
                  ))}
                </div>
              ) : dashboard?.recent_claims.length ? (
                dashboard.recent_claims.map((claim) => (
                  <button
                    key={claim.id}
                    type="button"
                    onClick={() => navigate("/app/workspace")}
                    className="flex w-full items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
                  >
                    <div>
                      <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                        {claim.patient_name}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        Service date {formatDate(claim.service_date)} · Updated{" "}
                        {formatDateTime(claim.updated_at)}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        {claim.insurance_company_name ?? "Insurance TBD"}
                      </div>
                    </div>
                    <span
                      className={cn(
                        "rounded-full px-3 py-1 text-xs font-semibold",
                        claim.claim_status === "final"
                          ? "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
                          : "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200"
                      )}
                    >
                      {claim.claim_status === "final" ? "Final" : "Draft"}
                    </span>
                  </button>
                ))
              ) : (
                <div className="text-sm text-slate-500">No recent claims yet.</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
