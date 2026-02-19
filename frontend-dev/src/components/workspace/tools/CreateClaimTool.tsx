import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

import { createClaimDraft } from "@/api/claims";
import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ClaimDraftPreview } from "@/components/workspace/types";
import { ApiError } from "@/lib/api/errors";
import type { ClaimDTO } from "@/types/claim";

const requiredNotice = "Please fill in all required fields.";

type CreateClaimToolProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  draftPreview: Partial<ClaimDraftPreview>;
  onDraftChange: Dispatch<SetStateAction<Partial<ClaimDraftPreview>>>;
  onUnauthorized: () => void;
  onClaimCreated: (claim: ClaimDTO) => void;
  sessionId?: number | null;
};

export default function CreateClaimTool({
  open,
  onOpenChange,
  draftPreview,
  onDraftChange,
  onUnauthorized,
  onClaimCreated,
  sessionId,
}: CreateClaimToolProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setError(null);
      setFormError(null);
    }
  }, [open]);

  const updatePatient = (field: "first_name" | "last_name" | "date_of_birth", value: string) => {
    if (formError) {
      setFormError(null);
    }
    onDraftChange((prev) => ({
      ...prev,
      patient: {
        ...(prev.patient ?? {}),
        [field]: value,
      },
    }));
  };

  const updateField = (field: "insurance_company_id" | "service_date", value: string) => {
    if (formError) {
      setFormError(null);
    }
    onDraftChange((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = async () => {
    const firstName = draftPreview.patient?.first_name?.trim() ?? "";
    const lastName = draftPreview.patient?.last_name?.trim() ?? "";
    const dateOfBirth = draftPreview.patient?.date_of_birth?.trim() ?? "";
    const insuranceValue = draftPreview.insurance_company_id?.toString().trim() ?? "";
    const serviceDate = draftPreview.service_date?.trim() ?? "";

    if (!firstName || !lastName || !insuranceValue || !serviceDate) {
      setFormError(requiredNotice);
      return;
    }

    const insuranceId = Number(insuranceValue);
    if (!Number.isFinite(insuranceId)) {
      setFormError("Insurance company ID must be a number.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setFormError(null);

    try {
      const claim = await createClaimDraft({
        patient: {
          first_name: firstName,
          last_name: lastName,
          date_of_birth: dateOfBirth || null,
        },
        insurance_company_id: insuranceId,
        service_date: serviceDate,
        session_id: sessionId ?? null,
      });
      onClaimCreated(claim);
      onOpenChange(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
        return;
      }
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="left-auto right-0 top-0 h-full w-full max-w-md translate-x-0 translate-y-0 rounded-none rounded-l-3xl border-l border-slate-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
        <DialogHeader>
          <DialogTitle>Create Claim</DialogTitle>
          <DialogDescription className="dark:text-slate-300">
            Enter the draft claim header details. Required fields are marked.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
            First name *
            <input
              type="text"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              value={draftPreview.patient?.first_name ?? ""}
              onChange={(event) => updatePatient("first_name", event.target.value)}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Last name *
            <input
              type="text"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              value={draftPreview.patient?.last_name ?? ""}
              onChange={(event) => updatePatient("last_name", event.target.value)}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Date of birth
            <input
              type="date"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              value={draftPreview.patient?.date_of_birth ?? ""}
              onChange={(event) => updatePatient("date_of_birth", event.target.value)}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Insurance company ID *
            <input
              type="number"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              value={draftPreview.insurance_company_id ?? ""}
              onChange={(event) => updateField("insurance_company_id", event.target.value)}
            />
          </label>
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Service date *
            <input
              type="date"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              value={draftPreview.service_date ?? ""}
              onChange={(event) => updateField("service_date", event.target.value)}
            />
          </label>
        </div>

        {formError ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
            {formError}
          </div>
        ) : null}

        {error ? <ErrorNotice error={error} /> : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Creating..." : "Create Draft"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
