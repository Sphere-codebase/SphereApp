import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { listAIHistory } from "@/api/aiHistory";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import { useDebouncedValue } from "@/lib/hooks/useDebouncedValue";
import { queryKeys } from "@/lib/query/keys";
import type { AIHistoryItemDTO } from "@/types/aiHistory";

const PAGE_LIMIT = 25;

const ACTION_OPTIONS = [
  { value: "", label: "All actions" },
  { value: "ai_proposal_confirmed", label: "AI proposal confirmed" },
  { value: "ai_proposal_rejected", label: "AI proposal rejected" },
  { value: "claim.finalized", label: "Claim finalized" },
  { value: "claim.pdf_generated", label: "PDF generated" },
];

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

function extractCode(diff?: Record<string, unknown> | null): string {
  if (!diff) {
    return "—";
  }
  const candidates = [
    diff.code,
    diff.mcp_code,
    diff.diagnosis_code,
    (diff.payload as Record<string, unknown> | undefined)?.code,
    (diff.payload as Record<string, unknown> | undefined)?.mcp_code,
    (diff.payload as Record<string, unknown> | undefined)?.diagnosis_code,
    (diff.proposed_changes as Record<string, unknown> | undefined)?.code,
  ];
  const first = candidates.find((value) => typeof value === "string" && value.trim());
  if (typeof first === "string") {
    return first;
  }
  const listCandidate =
    diff.codes || diff.mcp_codes || diff.diagnosis_codes ||
    (diff.payload as Record<string, unknown> | undefined)?.codes;
  if (Array.isArray(listCandidate)) {
    return listCandidate.filter((value) => typeof value === "string").join(", ");
  }
  return "—";
}

function extractConfidence(diff?: Record<string, unknown> | null): string {
  if (!diff) {
    return "—";
  }
  const value =
    diff.confidence ??
    diff.score ??
    (diff.payload as Record<string, unknown> | undefined)?.confidence;
  if (typeof value === "number") {
    return `${Math.round(value * 100)}%`;
  }
  if (typeof value === "string") {
    return value;
  }
  return "—";
}

function decisionFromAction(action: string): string {
  if (action.includes("rejected")) {
    return "Rejected";
  }
  if (action.includes("confirmed")) {
    return "Confirmed";
  }
  if (action === "claim.finalized") {
    return "Finalized";
  }
  if (action === "claim.pdf_generated") {
    return "Generated";
  }
  return "—";
}

export default function AIHistoryPage() {
  const { me, logout, hasRole } = useAuth();
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [claimId, setClaimId] = useState("");
  const [action, setAction] = useState("");
  const debouncedDoctorId = useDebouncedValue(doctorId, 300);
  const debouncedClaimId = useDebouncedValue(claimId, 300);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const filters = useMemo(() => {
    const doctorValue = debouncedDoctorId ? Number(debouncedDoctorId) : undefined;
    const claimValue = debouncedClaimId ? Number(debouncedClaimId) : undefined;
    return {
      from: fromDate || undefined,
      to: toDate || undefined,
      doctor_id: Number.isFinite(doctorValue) ? doctorValue : undefined,
      claim_id: Number.isFinite(claimValue) ? claimValue : undefined,
      action: action || undefined,
    };
  }, [fromDate, toDate, debouncedDoctorId, debouncedClaimId, action]);

  useEffect(() => {
    setOffset(0);
  }, [filters]);

  const {
    data,
    isLoading,
    isFetching,
    error,
  } = useQuery<{ items: AIHistoryItemDTO[]; total: number }, ApiError>({
    queryKey: queryKeys.auditLogs("clinic", { ...filters, limit: PAGE_LIMIT, offset }),
    queryFn: () => listAIHistory({ ...filters, limit: PAGE_LIMIT, offset }),
    staleTime: 30_000,
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

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              {me?.clinic_name ?? "Clinic"}
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              AI History
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/app/dashboard")}
            >
              Dashboard
            </Button>
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
            {hasRole("chief_doctor") || hasRole("clinic_admin") ? (
              <label className="flex flex-col gap-1">
                Doctor ID
                <input
                  type="number"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={doctorId}
                  onChange={(event) => setDoctorId(event.target.value)}
                  placeholder="Doctor ID"
                />
              </label>
            ) : null}
            <label className="flex flex-col gap-1">
              Claim ID
              <input
                type="number"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={claimId}
                onChange={(event) => setClaimId(event.target.value)}
                placeholder="Claim ID"
              />
            </label>
            <label className="flex flex-col gap-1">
              Action
              <select
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={action}
                onChange={(event) => setAction(event.target.value)}
              >
                {ACTION_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </CardContent>
        </Card>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            Unable to load AI history.
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Audit Log</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {isFetching && !isLoading ? (
              <div className="text-xs text-slate-500">Refreshing...</div>
            ) : null}
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={`history-skeleton-${index}`}
                    className="h-14 rounded-2xl bg-slate-100 dark:bg-slate-800"
                  />
                ))}
              </div>
            ) : items.length === 0 ? (
              <div className="text-sm text-slate-500">No AI actions found.</div>
            ) : (
              items.map((item) => {
                const expanded = expandedIds.has(item.id);
                const codeLabel = extractCode(item.diff_json ?? null);
                const confidence = extractConfidence(item.diff_json ?? null);
                const decision = decisionFromAction(item.action);
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
                          <div className="text-xs uppercase text-slate-400">Doctor</div>
                          <div>{item.actor_name ?? item.actor_id ?? "—"}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Action</div>
                          <div>{item.action}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Claim</div>
                          <button
                            type="button"
                            className="font-semibold text-emerald-700 hover:underline dark:text-emerald-300"
                            onClick={() => {
                              if (item.entity_id) {
                                navigate(`/app/workspace?claimId=${item.entity_id}`);
                              }
                            }}
                          >
                            {item.entity_id ?? "—"}
                          </button>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Code</div>
                          <div>{codeLabel}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase text-slate-400">Decision</div>
                          <div>{decision}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-xs text-slate-500">Confidence: {confidence}</div>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => toggleExpanded(item.id)}
                        >
                          {expanded ? "Hide" : "View"}
                        </Button>
                      </div>
                    </div>
                    {expanded ? (
                      <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                        <div className="mb-2 text-[11px] uppercase text-slate-400">diff_json</div>
                        <pre className="max-h-60 overflow-auto whitespace-pre-wrap">
                          {JSON.stringify(item.diff_json ?? {}, null, 2)}
                        </pre>
                        {item.request_id ? (
                          <div className="mt-2 text-[11px] text-slate-500">
                            Request ID: {item.request_id}
                          </div>
                        ) : null}
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
            Showing {items.length} of {total} actions
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
