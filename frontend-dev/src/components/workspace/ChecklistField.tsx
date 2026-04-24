import { cn } from "@/lib/utils";
import type { VirtualClaimChecklistValueDTO } from "@/types/virtualClaim";

type ChecklistFieldProps = {
  field: VirtualClaimChecklistValueDTO;
  label: string;
};

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

function uiStatus(
  status: VirtualClaimChecklistValueDTO["status"]
): "filled" | "missing" | "unknown" {
  if (status === "missing") {
    return "missing";
  }
  if (status === "present" || status === "derived") {
    return "filled";
  }
  return "unknown";
}

function sourceLabel(
  source: VirtualClaimChecklistValueDTO["source_type"]
): "database" | "user" | "policy" | "inferred" {
  if (source === "database" || source === "user" || source === "policy") {
    return source;
  }
  return "inferred";
}

export default function ChecklistField({ field, label }: ChecklistFieldProps) {
  const status = uiStatus(field.status);
  const source = sourceLabel(field.source_type);
  const value = formatValue(field.value);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            {field.label ?? label}
          </div>
          <div className="mt-1 break-words text-sm text-slate-600 dark:text-slate-300">
            {value}
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]",
            status === "filled" &&
              "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
            status === "missing" &&
              "bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-200",
            status === "unknown" &&
              "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200"
          )}
        >
          {status}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <span>Source: {source}</span>
        <span>{field.required ? "Required" : "Optional"}</span>
      </div>
    </div>
  );
}
