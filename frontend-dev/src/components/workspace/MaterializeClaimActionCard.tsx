import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type MaterializeClaimActionCardProps = {
  proposal: Record<string, unknown>;
  proposalError: string | null;
  isConfirming: boolean;
  isReadOnly: boolean;
  onConfirm: () => void;
  onReject: () => void;
};

function getSummaryField(
  summary: Record<string, unknown> | null,
  key: string
): string {
  if (!summary) {
    return "—";
  }
  const value = summary[key];
  return typeof value === "string" && value.trim() ? value : "—";
}

export default function MaterializeClaimActionCard({
  proposal,
  proposalError,
  isConfirming,
  isReadOnly,
  onConfirm,
  onReject,
}: MaterializeClaimActionCardProps) {
  const proposedChanges =
    proposal.proposed_changes && typeof proposal.proposed_changes === "object"
      ? (proposal.proposed_changes as Record<string, unknown>)
      : null;
  const summary =
    proposedChanges?.summary && typeof proposedChanges.summary === "object"
      ? (proposedChanges.summary as Record<string, unknown>)
      : null;

  return (
    <Card className="border-amber-200 bg-amber-50">
      <CardHeader>
        <CardTitle>Materialize Virtual Claim</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-amber-950">
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-white px-3 py-3">
          <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
          <div>
            <div className="font-semibold">Checklist is ready to draft.</div>
            <div className="mt-1 text-xs text-slate-600">
              Confirm to create the real draft claim from the session-backed virtual checklist.
            </div>
          </div>
        </div>

        <div className="grid gap-2 rounded-2xl border border-amber-200 bg-white p-3 text-xs text-slate-700">
          <div>
            <span className="font-semibold">Patient:</span>{" "}
            {getSummaryField(summary, "patient_name")}
          </div>
          <div>
            <span className="font-semibold">Payer:</span>{" "}
            {getSummaryField(summary, "payer_name")}
          </div>
          <div>
            <span className="font-semibold">Procedure:</span>{" "}
            {getSummaryField(summary, "procedure_code")}
          </div>
          <div>
            <span className="font-semibold">Service Date:</span>{" "}
            {getSummaryField(summary, "service_date")}
          </div>
        </div>

        {proposalError ? (
          <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5" />
            <span>{proposalError}</span>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={onConfirm}
            disabled={isReadOnly || isConfirming}
          >
            {isConfirming ? "Confirming..." : "Create Draft Claim"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onReject}
            disabled={isReadOnly || isConfirming}
          >
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
