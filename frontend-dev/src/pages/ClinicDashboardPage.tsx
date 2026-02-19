import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getClinicDashboard } from "@/api/clinicAdmin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import type { ClinicDashboardDTO } from "@/types/clinicAdmin";

function toDateInput(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function ClinicDashboardPage() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<ClinicDashboardDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [cache, setCache] = useState<Record<string, ClinicDashboardDTO>>({});

  const defaultTo = useMemo(() => new Date(), []);
  const defaultFrom = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() - 30);
    return date;
  }, []);

  const [fromDate, setFromDate] = useState(toDateInput(defaultFrom));
  const [toDate, setToDate] = useState(toDateInput(defaultTo));

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const loadDashboard = useCallback(async () => {
    const cacheKey = `${fromDate}:${toDate}`;
    if (cache[cacheKey]) {
      setData(cache[cacheKey]);
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await getClinicDashboard({ from: fromDate, to: toDate });
      setData(response);
      setCache((prev) => ({ ...prev, [cacheKey]: response }));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load clinic dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, [fromDate, toDate, cache, handleUnauthorized]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              {me?.clinic_name ?? "Clinic"}
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Clinic Dashboard
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {me?.role === "clinic_admin" ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate("/app/clinic/doctors")}
              >
                Manage Doctors
              </Button>
            ) : null}
            <Button type="button" variant="outline" onClick={() => navigate("/app/clinic/audit")}>
              View Audit Logs
            </Button>
          </div>
        </header>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Date Range</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-4">
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
            <Button type="button" onClick={loadDashboard} disabled={isLoading}>
              {isLoading ? "Loading..." : "Refresh"}
            </Button>
          </CardContent>
        </Card>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Total Claims", value: data?.kpis.total_claims ?? 0 },
            { label: "Draft Claims", value: data?.kpis.draft_claims ?? 0 },
            { label: "Finalized Claims", value: data?.kpis.finalized_claims ?? 0 },
            { label: "Active Doctors", value: data?.kpis.active_doctors ?? 0 },
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

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Top Insurers</CardTitle>
          </CardHeader>
          <CardContent>
            {data?.top_insurers?.length ? (
              <div className="space-y-2 text-sm">
                {data.top_insurers.map((insurer) => (
                  <div key={insurer.insurance_company_id} className="flex items-center justify-between">
                    <span>{insurer.name}</span>
                    <span className="text-slate-500">{insurer.claim_count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">No insurer data.</div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Claims Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              {data?.claims_timeseries?.length ? (
                <div className="space-y-2 text-sm">
                  {data.claims_timeseries.map((point) => (
                    <div key={point.date} className="flex items-center justify-between">
                      <span>{formatDate(point.date)}</span>
                      <span className="text-slate-500">{point.count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">No claims in range.</div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">AI Activity Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              {data?.ai_timeseries?.length ? (
                <div className="space-y-2 text-sm">
                  {data.ai_timeseries.map((point) => (
                    <div key={point.date} className="flex items-center justify-between">
                      <span>{formatDate(point.date)}</span>
                      <span className="text-slate-500">{point.count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">No AI activity in range.</div>
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data?.recent_activity?.length ? (
              data.recent_activity.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                >
                  <div className="text-xs text-slate-500">{formatDateTime(item.created_at)}</div>
                  <div className="mt-1 font-semibold text-slate-900 dark:text-white">
                    {item.action}
                  </div>
                  <div className="text-xs text-slate-500">
                    {item.actor_name ?? item.actor_id ?? "—"} · {item.entity} {item.entity_id ?? ""}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-slate-500">No recent activity.</div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
