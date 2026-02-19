import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { exportPlatformAudit, listPlatformAudit, listPlatformClinics } from "@/api/platformAdmin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import { useDebouncedValue } from "@/lib/hooks/useDebouncedValue";
import { queryKeys } from "@/lib/query/keys";
import type { PlatformAuditItemDTO, PlatformClinicDTO } from "@/types/platformAdmin";

const PAGE_LIMIT = 25;

const ENTITY_OPTIONS = ["", "claim", "patient", "chat_session", "policy_link", "clinic", "user"];

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function PlatformAuditPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [exportOpen, setExportOpen] = useState(false);
  const [includeDiff, setIncludeDiff] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [clinicId, setClinicId] = useState("");
  const [entity, setEntity] = useState("");
  const [actorId, setActorId] = useState("");
  const [action, setAction] = useState("");
  const debouncedAction = useDebouncedValue(action, 300);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const { data: clinicsData } = useQuery<{ items: PlatformClinicDTO[] }, ApiError>({
    queryKey: queryKeys.platformClinics("audit-filter"),
    queryFn: () => listPlatformClinics({ limit: 100, offset: 0 }),
    staleTime: 300_000,
    onError: (err) => {
      if (err.status === 401 || err.status === 403) {
        handleUnauthorized();
      }
    },
  });
  const clinics = clinicsData?.items ?? [];

  const filters = useMemo(
    () => ({
      from: fromDate || undefined,
      to: toDate || undefined,
      clinic_id: clinicId ? Number(clinicId) : undefined,
      entity: entity || undefined,
      actor_id: actorId ? Number(actorId) : undefined,
      action: debouncedAction || undefined,
    }),
    [fromDate, toDate, clinicId, entity, actorId, debouncedAction]
  );

  useEffect(() => {
    setOffset(0);
  }, [filters]);

  const {
    data,
    isLoading,
    isFetching,
    error,
  } = useQuery<{ items: PlatformAuditItemDTO[]; total: number }, ApiError>({
    queryKey: queryKeys.auditLogs("platform", { ...filters, limit: PAGE_LIMIT, offset }),
    queryFn: () => listPlatformAudit({ ...filters, limit: PAGE_LIMIT, offset }),
    staleTime: 15_000,
    onError: (err) => {
      if (err.status === 401 || err.status === 403) {
        handleUnauthorized();
      }
    },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

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

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const result = await exportPlatformAudit({
        from: fromDate || undefined,
        to: toDate || undefined,
        clinic_id: clinicId ? Number(clinicId) : undefined,
        entity: entity || undefined,
        actor_id: actorId ? Number(actorId) : undefined,
        action: action || undefined,
        include_diff: includeDiff,
      });
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename ?? "platform_audit_logs.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setExportOpen(false);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setExportError("Unable to export platform audit logs.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Platform Admin
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Platform Audit
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/app/platform/clinics")}>
              Clinics
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/app/platform/usage")}>
              Usage Overview
            </Button>
            <Button type="button" onClick={() => setExportOpen(true)}>
              Export CSV
            </Button>
          </div>
        </header>

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Filters</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-2 lg:grid-cols-6">
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
              Actor ID
              <input
                type="number"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={actorId}
                onChange={(event) => setActorId(event.target.value)}
                placeholder="Actor ID"
              />
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

        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
          Some fields were redacted for privacy.
        </div>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            Unable to load platform audit logs.
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Audit Logs</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {isFetching && !isLoading ? (
              <div className="text-xs text-slate-500">Refreshing...</div>
            ) : null}
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={`platform-audit-skeleton-${index}`} className="h-14 rounded-2xl bg-slate-100 dark:bg-slate-800" />
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
                      <div className="grid flex-1 gap-1 md:grid-cols-6">
                        <div>
                          <div className="text-xs uppercase text-slate-400">Timestamp</div>
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">
                            {formatDateTime(item.created_at)}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Clinic</div>
                          <div>{item.clinic_name ?? item.clinic_id}</div>
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
                      <div className="mt-3 space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <div className="text-[10px] uppercase text-slate-400">Request ID</div>
                            <div className="text-xs text-slate-600 dark:text-slate-300">
                              {item.request_id ?? "—"}
                            </div>
                          </div>
                          {item.request_id ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => void navigator.clipboard?.writeText(item.request_id ?? "")}
                            >
                              Copy
                            </Button>
                          ) : null}
                        </div>
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

        <Dialog open={exportOpen} onOpenChange={setExportOpen}>
          <DialogContent className="max-w-lg dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
            <DialogHeader>
              <DialogTitle>Export Platform Audit Logs</DialogTitle>
              <DialogDescription className="dark:text-slate-300">
                Export a CSV using the current filters.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-3 text-sm text-slate-600 dark:text-slate-300">
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
              <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <input
                  type="checkbox"
                  checked={includeDiff}
                  onChange={(event) => setIncludeDiff(event.target.checked)}
                />
                Include diff_json (masked)
              </label>
              {exportError ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
                  {exportError}
                </div>
              ) : null}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setExportOpen(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={handleExport} disabled={exporting}>
                {exporting ? "Generating..." : "Download CSV"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

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
              disabled={offset === 0 || isLoading || isFetching}
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
              disabled={offset + PAGE_LIMIT >= total || isLoading || isFetching}
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
