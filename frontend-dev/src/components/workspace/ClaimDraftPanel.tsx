import { useEffect, useMemo, useState } from "react";

import type { ClaimDraftPreview } from "@/components/workspace/types";
import CodeSearchDiagnosis from "@/components/workspace/CodeSearchDiagnosis";
import CodeSearchMCP from "@/components/workspace/CodeSearchMCP";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  ClaimDTO,
  ClaimFinancialSummaryDTO,
  ClaimRequirementsDTO,
  DiagnosisCodeDTO,
  MCPCodeDTO,
} from "@/types/claim";
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

function formatCurrency(amount?: number | null): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return "—";
  }
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
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
  showAdmin: boolean;
  onOpenUploadPdf: () => void;
  onOpenCreateClaim: () => void;
  onAddMcpCode: (code: MCPCodeDTO) => void;
  onRemoveMcpCode: (code: MCPCodeDTO) => void;
  onAddDiagnosisCode: (code: DiagnosisCodeDTO) => void;
  onRemoveDiagnosisCode: (code: DiagnosisCodeDTO) => void;
  onFinalizeClaim: () => void;
  isFinalizing: boolean;
  onGeneratePdf: () => void;
  isGeneratingPdf: boolean;
  pdfPreviewUrl: string | null;
  onClosePdfPreview: () => void;
  financialSummary: ClaimFinancialSummaryDTO | null;
  isLoadingFinancial: boolean;
  financialError: string | null;
  onRefreshFinancial: () => void;
  requirements: ClaimRequirementsDTO | null;
  isCheckingRequirements: boolean;
  requirementsError: string | null;
  onCheckRequirements: () => void;
};

export default function ClaimDraftPanel({
  currentClaim,
  draftPreview,
  isLoading,
  claimError,
  showAdmin,
  onOpenUploadPdf,
  onOpenCreateClaim,
  onAddMcpCode,
  onRemoveMcpCode,
  onAddDiagnosisCode,
  onRemoveDiagnosisCode,
  onFinalizeClaim,
  isFinalizing,
  onGeneratePdf,
  isGeneratingPdf,
  pdfPreviewUrl,
  onClosePdfPreview,
  financialSummary,
  isLoadingFinancial,
  financialError,
  onRefreshFinancial,
  requirements,
  isCheckingRequirements,
  requirementsError,
  onCheckRequirements,
}: ClaimDraftPanelProps) {
  const [activeTab, setActiveTab] = useState<"procedures" | "diagnoses" | "financial">(
    "procedures"
  );
  const [showFinalizeConfirm, setShowFinalizeConfirm] = useState(false);
  const [isPdfLoading, setIsPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState(false);

  useEffect(() => {
    if (pdfPreviewUrl) {
      setIsPdfLoading(true);
      setPdfError(false);
    }
  }, [pdfPreviewUrl]);

  const hasPreview = hasPreviewValues(draftPreview);
  const hasClaim = Boolean(currentClaim);
  const isFinal = currentClaim?.claim_status === "final";
  const isDisabled = !currentClaim || isFinal;
  const missingCount = requirements?.missing?.length ?? null;
  const completenessLabel =
    missingCount === null
      ? "Unknown"
      : missingCount === 0
        ? "Complete"
        : `${missingCount} missing`;

  if (!currentClaim && !hasPreview) {
    return (
      <aside className="flex flex-col gap-3 rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
        <div className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Tools
        </div>
        {isLoading ? <div className="text-xs text-slate-500">Loading claim...</div> : null}
        {claimError ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {claimError}
          </div>
        ) : null}
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

  const predictionMap = useMemo(() => {
    const entries = financialSummary?.predicted_per_mcp ?? [];
    return new Map(entries.map((entry) => [entry.mcp_code, entry]));
  }, [financialSummary]);

  const averageConfidence = useMemo(() => {
    const entries = financialSummary?.predicted_per_mcp ?? [];
    const confidences = entries
      .map((entry) => entry.confidence)
      .filter((value): value is number => typeof value === "number");
    if (confidences.length === 0) {
      return null;
    }
    const total = confidences.reduce((sum, value) => sum + value, 0);
    return total / confidences.length;
  }, [financialSummary]);

  const isFinancialLoading = isLoadingFinancial && !financialSummary;

  return (
    <aside className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">Claim Header</div>
        <div className="flex items-center gap-2">
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
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-200">
            {completenessLabel}
          </span>
        </div>
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

      <div className="flex flex-wrap gap-2">
        {!isFinal && currentClaim ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setShowFinalizeConfirm(true)}
            disabled={isFinalizing}
          >
            {isFinalizing ? "Finalizing..." : "Finalize Claim"}
          </Button>
        ) : null}
        {currentClaim ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onCheckRequirements}
            disabled={isCheckingRequirements}
          >
            {isCheckingRequirements ? "Checking..." : "Check Requirements"}
          </Button>
        ) : null}
        {currentClaim ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={onGeneratePdf}
            disabled={isGeneratingPdf}
          >
            {isGeneratingPdf ? "Generating..." : "Generate PDF"}
          </Button>
        ) : null}
        {pdfPreviewUrl ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onClosePdfPreview}
          >
            Close Preview
          </Button>
        ) : null}
      </div>

      {isLoading ? (
        <div className="text-xs text-slate-500">Loading claim...</div>
      ) : null}

      {claimError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          {claimError}
        </div>
      ) : null}
      {requirementsError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          {requirementsError}
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
        <button
          type="button"
          className={cn(
            "flex-1 rounded-2xl px-3 py-2 text-xs font-semibold transition",
            activeTab === "financial"
              ? "bg-white text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100"
              : "text-slate-500 hover:text-slate-700 dark:text-slate-400"
          )}
          onClick={() => setActiveTab("financial")}
          disabled={!hasClaim}
        >
          Financial
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
                  <div className="flex items-center gap-2">
                    {(() => {
                      if (isFinancialLoading) {
                        return (
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-300">
                            Loading...
                          </span>
                        );
                      }
                      const prediction = predictionMap.get(code.code);
                      if (!prediction) {
                        return (
                          <span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/20 dark:text-amber-200">
                            No prediction
                          </span>
                        );
                      }
                      const confidence =
                        typeof prediction.confidence === "number"
                          ? `${Math.round(prediction.confidence * 100)}%`
                          : "—";
                      return (
                        <span className="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200">
                          {formatCurrency(prediction.predicted_paid_amount)} · {confidence}
                        </span>
                      );
                    })()}
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
      ) : activeTab === "diagnoses" ? (
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
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs text-slate-500">
              {financialSummary ? `Updated ${formatDate(financialSummary.updated_at)}` : "—"}
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onRefreshFinancial}
              disabled={!hasClaim || isLoadingFinancial}
            >
              {isLoadingFinancial ? "Refreshing..." : "Refresh Predictions"}
            </Button>
          </div>

          {financialError ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
              {financialError}
            </div>
          ) : null}

          {isLoadingFinancial && !financialSummary ? (
            <div className="text-xs text-slate-500">Loading financial insights...</div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">
                Predicted Total
              </div>
              <div className="mt-2 text-base font-semibold text-slate-900 dark:text-white">
                {formatCurrency(financialSummary?.predicted_total_paid_amount ?? null)}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">
                Avg Confidence
              </div>
              <div className="mt-2 text-base font-semibold text-slate-900 dark:text-white">
                {averageConfidence === null
                  ? "—"
                  : `${Math.round(averageConfidence * 100)}%`}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">
                Flags
              </div>
              <div className="mt-2 text-base font-semibold text-slate-900 dark:text-white">
                {financialSummary?.flags?.length ?? 0}
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-600 dark:text-slate-300">
              Per-Procedure Predictions
            </div>
            {mcpCodes.length === 0 ? (
              <div className="text-xs text-slate-500">No procedures to evaluate.</div>
            ) : (
              <div className="space-y-2">
                {mcpCodes.map((code) => {
                  const prediction = predictionMap.get(code.code);
                  return (
                    <div
                      key={`financial-${code.code}`}
                      className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">
                            {code.code}
                          </div>
                          <div className="text-xs text-slate-500 dark:text-slate-400">
                            {code.description || "No description"}
                          </div>
                        </div>
                        <div className="text-right text-xs">
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">
                            {prediction
                              ? formatCurrency(prediction.predicted_paid_amount)
                              : "—"}
                          </div>
                          <div className="text-[10px] text-slate-500 dark:text-slate-400">
                            {prediction?.confidence !== undefined && prediction?.confidence !== null
                              ? `${Math.round(prediction.confidence * 100)}% confidence`
                              : "No confidence"}
                          </div>
                        </div>
                      </div>
                      {prediction?.explanation ? (
                        <details className="mt-2 text-[11px] text-slate-500">
                          <summary className="cursor-pointer">Explanation</summary>
                          <div className="mt-1 whitespace-pre-wrap text-slate-600 dark:text-slate-300">
                            {prediction.explanation}
                          </div>
                        </details>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-600 dark:text-slate-300">
              Risk Flags
            </div>
            {financialSummary?.flags?.length ? (
              financialSummary.flags.map((flag) => (
                <div
                  key={flag.code}
                  className={cn(
                    "rounded-2xl border px-3 py-2 text-xs",
                    flag.severity === "high"
                      ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200"
                      : flag.severity === "warn"
                        ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200"
                        : "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
                  )}
                >
                  {flag.message}
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500">No risk flags detected.</div>
            )}
          </div>
        </div>
      )}

      <Dialog open={showFinalizeConfirm} onOpenChange={setShowFinalizeConfirm}>
        <DialogContent className="max-w-md dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
          <DialogHeader>
            <DialogTitle>Finalize claim?</DialogTitle>
            <DialogDescription className="dark:text-slate-300">
              This will lock editing in the workspace.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowFinalizeConfirm(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                setShowFinalizeConfirm(false);
                onFinalizeClaim();
              }}
              disabled={isFinalizing}
            >
              Finalize
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(pdfPreviewUrl)} onOpenChange={(open) => !open && onClosePdfPreview()}>
        <DialogContent className="max-w-4xl dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
          <DialogHeader>
            <DialogTitle>Claim PDF Preview</DialogTitle>
            <DialogDescription className="dark:text-slate-300">
              Preview the latest generated PDF.
            </DialogDescription>
          </DialogHeader>
          {pdfPreviewUrl ? (
            <div className="h-[60vh] overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
              {isPdfLoading ? (
                <div className="flex h-full items-center justify-center text-xs text-slate-500">
                  Loading PDF...
                </div>
              ) : null}
              {pdfError ? (
                <div className="flex h-full items-center justify-center text-xs text-rose-600">
                  Failed to load PDF preview.
                </div>
              ) : null}
              <iframe
                title="Claim PDF"
                src={pdfPreviewUrl}
                loading="lazy"
                className={cn(
                  "h-full w-full transition-opacity",
                  isPdfLoading || pdfError ? "opacity-0" : "opacity-100"
                )}
                onLoad={() => setIsPdfLoading(false)}
                onError={() => {
                  setIsPdfLoading(false);
                  setPdfError(true);
                }}
              />
            </div>
          ) : null}
          <DialogFooter>
            {pdfPreviewUrl ? (
              <Button type="button" variant="outline" asChild>
                <a href={pdfPreviewUrl} target="_blank" rel="noreferrer">
                  Open in new tab
                </a>
              </Button>
            ) : null}
            <Button type="button" onClick={onClosePdfPreview}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
