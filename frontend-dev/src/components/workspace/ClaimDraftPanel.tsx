import { useMemo, useState } from "react";

import type { ClaimDraftPreview } from "@/components/workspace/types";
import CodeSearchDiagnosis from "@/components/workspace/CodeSearchDiagnosis";
import CodeSearchMCP from "@/components/workspace/CodeSearchMCP";
import { Button } from "@/components/ui/button";
import type { ClaimDTO, DiagnosisCodeDTO, MCPCodeDTO } from "@/types/claim";
import { cn } from "@/lib/utils";

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

function formatName(first?: string, last?: string): string {
  const name = [first, last].filter(Boolean).join(" ");
  return name || "—";
}

function hasPreviewValues(preview: Partial<ClaimDraftPreview>): boolean {
  return Boolean(
    preview.patient?.first_name ||
      preview.patient?.last_name ||
      preview.patient?.date_of_birth ||
      preview.insurance_company_id ||
      preview.service_date
  );
}

type ClaimDraftPanelProps = {
  currentClaim: ClaimDTO | null;
  draftPreview: Partial<ClaimDraftPreview>;
  isLoading: boolean;
  claimError: string | null;
  onAddMcpCode: (code: MCPCodeDTO) => void;
  onRemoveMcpCode: (code: MCPCodeDTO) => void;
  onAddDiagnosisCode: (code: DiagnosisCodeDTO) => void;
  onRemoveDiagnosisCode: (code: DiagnosisCodeDTO) => void;
};

export default function ClaimDraftPanel({
  currentClaim,
  draftPreview,
  isLoading,
  claimError,
  onAddMcpCode,
  onRemoveMcpCode,
  onAddDiagnosisCode,
  onRemoveDiagnosisCode,
}: ClaimDraftPanelProps) {
  const [activeTab, setActiveTab] = useState<"procedures" | "diagnoses">(
    "procedures"
  );

  const hasPreview = hasPreviewValues(draftPreview);
  const hasClaim = Boolean(currentClaim);
  const isFinal = currentClaim?.claim_status === "final";
  const isDisabled = !currentClaim || isFinal;

  if (!currentClaim && !hasPreview) {
    return (
      <aside className="flex flex-col gap-3 rounded-3xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Claim Draft
        </div>
        {isLoading ? <div className="text-xs text-slate-500">Loading claim...</div> : null}
        {claimError ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {claimError}
          </div>
        ) : null}
        <div>No active claim. Use Tools → Create Claim.</div>
      </aside>
    );
  }

  const patient = hasClaim ? currentClaim?.patient : draftPreview.patient;
  const insurance = hasClaim
    ? currentClaim?.insurance_company_id
    : draftPreview.insurance_company_id;
  const serviceDate = hasClaim ? currentClaim?.service_date : draftPreview.service_date;
  const status = hasClaim
    ? currentClaim?.claim_status === "final"
      ? "Final"
      : "Draft"
    : "Draft (unsaved)";
  const insuranceLabel =
    insurance === 0 ? "0" : insurance ? String(insurance) : "—";

  const mcpCodes = useMemo(() => currentClaim?.mcp_codes ?? [], [currentClaim]);
  const diagnosisCodes = useMemo(
    () => currentClaim?.diagnosis_codes ?? [],
    [currentClaim]
  );

  return (
    <aside
      className={cn(
        "flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200",
        isFinal && "pointer-events-none opacity-60"
      )}
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">Claim Header</div>
        <span
          className={cn(
            "rounded-full px-3 py-1 text-xs font-semibold",
            status.includes("Final")
              ? "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
              : "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200"
          )}
        >
          {status}
        </span>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
        <div className="text-sm font-semibold text-slate-900 dark:text-white">
          {formatName(patient?.first_name, patient?.last_name)}
        </div>
        <div className="mt-1">DOB: {formatDate(patient?.date_of_birth)}</div>
        <div className="mt-2 space-y-1">
          <div>Insurance: {insuranceLabel}</div>
          <div>Service date: {formatDate(serviceDate)}</div>
        </div>
      </div>

      {isFinal ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
          Claim is finalized. Editing disabled.
        </div>
      ) : null}

      {isLoading ? (
        <div className="text-xs text-slate-500">Loading claim...</div>
      ) : null}

      {claimError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          {claimError}
        </div>
      ) : null}

      <div className="flex items-center gap-2 rounded-2xl bg-slate-100 p-1 text-xs dark:bg-slate-800">
        <button
          type="button"
          className={cn(
            "flex-1 rounded-2xl px-3 py-2 text-xs font-semibold transition",
            activeTab === "procedures"
              ? "bg-white text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100"
              : "text-slate-500 hover:text-slate-700 dark:text-slate-400"
          )}
          onClick={() => setActiveTab("procedures")}
          disabled={!hasClaim}
        >
          Procedures
        </button>
        <button
          type="button"
          className={cn(
            "flex-1 rounded-2xl px-3 py-2 text-xs font-semibold transition",
            activeTab === "diagnoses"
              ? "bg-white text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100"
              : "text-slate-500 hover:text-slate-700 dark:text-slate-400"
          )}
          onClick={() => setActiveTab("diagnoses")}
          disabled={!hasClaim}
        >
          Diagnoses
        </button>
      </div>

      {activeTab === "procedures" ? (
        <div className="flex flex-col gap-4">
          <div className="space-y-2">
            {mcpCodes.length === 0 ? (
              <div className="text-xs text-slate-500">No procedures yet.</div>
            ) : (
              mcpCodes.map((code) => (
                <div
                  key={code.code}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
                >
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      {code.code}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {code.description || "No description"}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onRemoveMcpCode(code)}
                    disabled={isDisabled}
                  >
                    Remove
                  </Button>
                </div>
              ))
            )}
          </div>
          <CodeSearchMCP
            disabled={isDisabled}
            existingCodes={mcpCodes.map((code) => code.code)}
            onAdd={onAddMcpCode}
          />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="space-y-2">
            {diagnosisCodes.length === 0 ? (
              <div className="text-xs text-slate-500">No diagnoses yet.</div>
            ) : (
              diagnosisCodes.map((code) => (
                <div
                  key={code.code}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
                >
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      {code.code}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {code.description || "No description"}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onRemoveDiagnosisCode(code)}
                    disabled={isDisabled}
                  >
                    Remove
                  </Button>
                </div>
              ))
            )}
          </div>
          <CodeSearchDiagnosis
            disabled={isDisabled}
            existingCodes={diagnosisCodes.map((code) => code.code)}
            onAdd={onAddDiagnosisCode}
          />
        </div>
      )}
    </aside>
  );
}
