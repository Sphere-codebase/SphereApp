import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listClinicAuditLogs, listClinicDoctors } from "@/api/clinicAdmin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import type { AuditLogItemDTO, DoctorUserDTO } from "@/types/clinicAdmin";

const PAGE_LIMIT = 25;

const ENTITY_OPTIONS = [
  "",
  "claim",
  "patient",
  "chat_session",
  "policy_link",
  "user",
  "claim_pdf",
];

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function ClinicAuditLogsPage() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState<AuditLogItemDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [doctorOptions, setDoctorOptions] = useState<DoctorUserDTO[]>([]);

  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [actorId, setActorId] = useState("");
  const [entity, setEntity] = useState("");
  const [action, setAction] = useState("");

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  useEffect(() => {
    listClinicDoctors()
      .then((response) => setDoctorOptions(response.items))
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          handleUnauthorized();
          return;
        }
        setDoctorOptions([]);
      });
  }, [handleUnauthorized]);

  const filters = useMemo(
    () => ({
      from: fromDate || undefined,
      to: toDate || undefined,
      actor_id: actorId ? Number(actorId) : undefined,
      entity: entity || undefined,
      action: action || undefined,
    }),
    [fromDate, toDate, actorId, entity, action]
  );

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listClinicAuditLogs({
        ...filters,
        limit: PAGE_LIMIT,
        offset,
      });
      setItems(response.items);
      setTotal(response.total);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load audit logs.");
    } finally {
      setIsLoading(false);
    }
  }, [filters, offset, handleUnauthorized]);

  useEffect(() => {
    setOffset(0);
  }, [filters]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  const toggleExpanded = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const totalPages = useMemo(() => Math.ceil(total / PAGE_LIMIT), [total]);
  const currentPage = useMemo(() => Math.floor(offset / PAGE_LIMIT) + 1, [offset]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              {me?.clinic_name ?? "Clinic"}
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Clinic Audit Logs
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/app/clinic")}
            >
              Clinic Dashboard
            </Button>
            {me?.role === "clinic_admin" ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate("/app/clinic/doctors")}
              >
                Manage Doctors
              </Button>
            ) : null}
          </div>
        </header>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Filters</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-2 lg:grid-cols-5">
            <label className="flex flex-col gap-1">
              From
              <input
                type="date"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1">
              To
              <input
                type="date"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1">
              Actor
              <select
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={actorId}
                onChange={(event) => setActorId(event.target.value)}
              >
                <option value="">All</option>
                {doctorOptions.map((doctor) => (
                  <option key={doctor.id} value={doctor.id}>
                    {doctor.full_name ?? doctor.email}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              Entity
              <select
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={entity}
                onChange={(event) => setEntity(event.target.value)}
              >
                {ENTITY_OPTIONS.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option || "All"}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              Action
              <input
                type="text"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={action}
                onChange={(event) => setAction(event.target.value)}
                placeholder="Action contains"
              />
            </label>
          </CardContent>
        </Card>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Audit Logs</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={`log-skeleton-${index}`}
                    className="h-14 rounded-2xl bg-slate-100 dark:bg-slate-800"
                  />
                ))}
              </div>
            ) : items.length === 0 ? (
              <div className="text-sm text-slate-500">No audit logs found.</div>
            ) : (
              items.map((item) => {
                const expanded = expandedIds.has(item.id);
                return (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="grid flex-1 gap-1 md:grid-cols-5">
                        <div>
                          <div className="text-xs uppercase text-slate-400">Timestamp</div>
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">
                            {formatDateTime(item.created_at)}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Actor</div>
                          <div>{item.actor_name ?? item.actor_id ?? "—"}</div>
                          <div className="text-xs text-slate-500">{item.actor_role ?? ""}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Action</div>
                          <div>{item.action}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Entity</div>
                          <div>
                            {item.entity} {item.entity_id ?? ""}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Request</div>
                          <div className="text-xs text-slate-500">{item.request_id ?? "—"}</div>
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => toggleExpanded(item.id)}
                      >
                        {expanded ? "Hide" : "View"}
                      </Button>
                    </div>
                    {expanded ? (
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                        <pre className="max-h-60 overflow-auto whitespace-pre-wrap">
                          {JSON.stringify(item.diff_json ?? {}, null, 2)}
                        </pre>
                      </div>
                    ) : null}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
          <div>
            Showing {items.length} of {total} logs
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
