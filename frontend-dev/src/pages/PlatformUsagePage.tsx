import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getPlatformUsage, listPlatformClinics } from "@/api/platformAdmin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import type { PlatformClinicDTO, PlatformUsageDTO } from "@/types/platformAdmin";

function toDateInput(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function PlatformUsagePage() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [usage, setUsage] = useState<PlatformUsageDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [clinics, setClinics] = useState<PlatformClinicDTO[]>([]);

  const defaultTo = useMemo(() => new Date(), []);
  const defaultFrom = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() - 30);
    return date;
  }, []);

  const [fromDate, setFromDate] = useState(toDateInput(defaultFrom));
  const [toDate, setToDate] = useState(toDateInput(defaultTo));
  const [clinicId, setClinicId] = useState("");

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  useEffect(() => {
    listPlatformClinics({ limit: 100, offset: 0 })
      .then((response) => setClinics(response.items))
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          handleUnauthorized();
          return;
        }
        setClinics([]);
      });
  }, [handleUnauthorized]);

  const loadUsage = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getPlatformUsage({
        from: fromDate,
        to: toDate,
        clinic_id: clinicId ? Number(clinicId) : undefined,
      });
      setUsage(response);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load platform usage.");
    } finally {
      setIsLoading(false);
    }
  }, [fromDate, toDate, clinicId, handleUnauthorized]);

  useEffect(() => {
    void loadUsage();
  }, [loadUsage]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Platform Admin
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Usage Overview
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/app/platform/clinics")}
            >
              Clinics
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/app/platform/audit")}
            >
              Platform Audit
            </Button>
          </div>
        </header>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Filters</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              From
              <input
                type="date"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              To
              <input
                type="date"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              Clinic
              <select
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={clinicId}
                onChange={(event) => setClinicId(event.target.value)}
              >
                <option value="">All clinics</option>
                {clinics.map((clinic) => (
                  <option key={clinic.id} value={clinic.id}>
                    {clinic.name}
                  </option>
                ))}
              </select>
            </label>
            <Button type="button" onClick={loadUsage} disabled={isLoading}>
              {isLoading ? "Loading..." : "Refresh"}
            </Button>
          </CardContent>
        </Card>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {[
            { label: "Claims Created", value: usage?.kpis.claims_created ?? 0 },
            { label: "Claims Finalized", value: usage?.kpis.claims_finalized ?? 0 },
            { label: "PDF Generated", value: usage?.kpis.pdf_generated ?? 0 },
            { label: "AI Actions", value: usage?.kpis.ai_actions ?? 0 },
            { label: "Active Clinics", value: usage?.kpis.active_clinics ?? 0 },
          ].map((item) => (
            <Card key={item.label} className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
              <CardContent className="p-4">
                <div className="text-xs uppercase text-slate-400">{item.label}</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">
                  {item.value}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Claims per Day</CardTitle>
            </CardHeader>
            <CardContent>
              {usage?.timeseries.claims?.length ? (
                <div className="space-y-2 text-sm">
                  {usage.timeseries.claims.map((point) => (
                    <div key={point.date} className="flex items-center justify-between">
                      <span>{formatDate(point.date)}</span>
                      <span className="text-slate-500">{point.count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">No claim data.</div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">PDFs per Day</CardTitle>
            </CardHeader>
            <CardContent>
              {usage?.timeseries.pdf?.length ? (
                <div className="space-y-2 text-sm">
                  {usage.timeseries.pdf.map((point) => (
                    <div key={point.date} className="flex items-center justify-between">
                      <span>{formatDate(point.date)}</span>
                      <span className="text-slate-500">{point.count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">No PDF data.</div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">AI Actions per Day</CardTitle>
            </CardHeader>
            <CardContent>
              {usage?.timeseries.ai?.length ? (
                <div className="space-y-2 text-sm">
                  {usage.timeseries.ai.map((point) => (
                    <div key={point.date} className="flex items-center justify-between">
                      <span>{formatDate(point.date)}</span>
                      <span className="text-slate-500">{point.count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">No AI data.</div>
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Top Clinics by Usage</CardTitle>
          </CardHeader>
          <CardContent>
            {usage?.top_clinics?.length ? (
              <div className="space-y-2 text-sm">
                {usage.top_clinics.map((clinic) => (
                  <div key={clinic.clinic_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{clinic.clinic_name}</span>
                    <span className="text-slate-500">
                      Claims {clinic.claims} · PDF {clinic.pdf} · AI {clinic.ai}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">No usage data.</div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
