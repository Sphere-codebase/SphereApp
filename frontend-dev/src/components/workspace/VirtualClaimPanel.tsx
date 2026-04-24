import { AlertTriangle, CheckCircle2, ClipboardList, FileWarning } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { VirtualClaimDTO, VirtualClaimFieldDTO } from "@/types/virtualClaim";

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

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return Object.prototype.toString.call(value);
  }
}

function Section({
  title,
  icon,
  items,
  emptyLabel,
}: {
  title: string;
  icon: JSX.Element;
  items: VirtualClaimFieldDTO[];
  emptyLabel: string;
}) {
  return (
    <section className="space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
        {icon}
        <span>{title}</span>
      </div>
      {items.length === 0 ? (
        <div className="text-xs text-slate-500 dark:text-slate-400">{emptyLabel}</div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.key}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="font-semibold text-slate-800 dark:text-slate-100">
                {item.label}
              </div>
              <div className="mt-1 text-slate-600 dark:text-slate-300">
                {formatValue(item.value)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

type VirtualClaimPanelProps = {
  virtualClaim: VirtualClaimDTO | null;
  isLoading: boolean;
  error: string | null;
  onOpenUploadPdf: () => void;
  onOpenCreateClaim: () => void;
};

export default function VirtualClaimPanel({
  virtualClaim,
  isLoading,
  error,
  onOpenUploadPdf,
  onOpenCreateClaim,
}: VirtualClaimPanelProps) {
  if (!virtualClaim && !isLoading) {
    return (
      <aside className="flex flex-col gap-3 rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Virtual Claim
        </div>
        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : (
          <div className="text-xs text-slate-500">No virtual claim state yet.</div>
        )}
        <div className="flex flex-col gap-2">
          <Button type="button" variant="outline" onClick={onOpenUploadPdf}>
            Upload PDF
          </Button>
          <Button type="button" variant="outline" onClick={onOpenCreateClaim}>
            Create Claim
          </Button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex min-h-[480px] min-h-0 flex-col gap-4 overflow-y-auto rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">Virtual Claim Checklist</div>
          <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Session-backed, deterministic draft state
          </div>
        </div>
        <span
          className={cn(
            "rounded-full px-3 py-1 text-xs font-semibold",
            virtualClaim?.readiness
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200"
              : "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200"
          )}
        >
          {virtualClaim?.readiness ? "READY" : "NOT READY"}
        </span>
      </div>

      {isLoading ? (
        <div className="text-xs text-slate-500 dark:text-slate-400">Loading checklist...</div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          {error}
        </div>
      ) : null}

      {virtualClaim ? (
        <>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-800 dark:bg-slate-950">
            <div className="grid gap-2">
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-100">Patient</div>
                <div>{virtualClaim.patient?.name ?? "—"}</div>
                <div>DOB: {formatDate(virtualClaim.patient?.date_of_birth ?? null)}</div>
              </div>
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-100">Payer</div>
                <div>{virtualClaim.payer?.name ?? "—"}</div>
              </div>
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-100">Procedure</div>
                <div>{virtualClaim.procedure?.code ?? "—"}</div>
                <div>{virtualClaim.procedure?.description ?? "—"}</div>
              </div>
              <div>
                <div className="font-semibold text-slate-800 dark:text-slate-100">
                  Readiness Reason
                </div>
                <div>{virtualClaim.readiness_reason ?? "—"}</div>
              </div>
              {virtualClaim.policy_summary?.policy_url ? (
                <div>
                  <div className="font-semibold text-slate-800 dark:text-slate-100">
                    Policy Link
                  </div>
                  <a
                    href={virtualClaim.policy_summary.policy_url}
                    target="_blank"
                    rel="noreferrer"
                    className="break-all text-sky-600 hover:text-sky-700 dark:text-sky-300"
                  >
                    {virtualClaim.policy_summary.policy_url}
                  </a>
                </div>
              ) : null}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Button type="button" variant="outline" onClick={onOpenUploadPdf}>
              Upload PDF
            </Button>
            <Button type="button" variant="outline" onClick={onOpenCreateClaim}>
              Manual Claim
            </Button>
          </div>

          <Section
            title="Filled"
            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
            items={virtualClaim.filled}
            emptyLabel="No completed checklist items yet."
          />
          <Section
            title="Missing"
            icon={<ClipboardList className="h-3.5 w-3.5" />}
            items={virtualClaim.missing}
            emptyLabel="No missing checklist items."
          />
          <Section
            title="Needs Review"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            items={virtualClaim.needs_review}
            emptyLabel="No review blockers."
          />
          <Section
            title="Policy Constraints"
            icon={<FileWarning className="h-3.5 w-3.5" />}
            items={virtualClaim.policy_constraints}
            emptyLabel="No stored payer constraints."
          />

          <section className="space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              Follow-Up Questions
            </div>
            {virtualClaim.follow_up_questions.length === 0 ? (
              <div className="text-xs text-slate-500 dark:text-slate-400">
                No follow-up questions queued.
              </div>
            ) : (
              <div className="space-y-2">
                {virtualClaim.follow_up_questions.map((item) => (
                  <div
                    key={item.question_key}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-900"
                  >
                    {item.prompt}
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}
    </aside>
  );
}
