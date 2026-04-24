import ChecklistSection, {
  type ChecklistSectionField,
} from "@/components/workspace/ChecklistSection";
import ReadinessBadge from "@/components/workspace/ReadinessBadge";
import { cn } from "@/lib/utils";
import type {
  VirtualClaimChecklistValueDTO,
  VirtualClaimDTO,
} from "@/types/virtualClaim";

function formatDate(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "No value yet";
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

function toFields(
  entries: Array<[key: string, label: string, field: VirtualClaimChecklistValueDTO | null | undefined]>
): ChecklistSectionField[] {
  return entries
    .filter(([, , field]) => Boolean(field))
    .map(([key, label, field]) => ({
      key,
      label,
      field: field as VirtualClaimChecklistValueDTO,
    }));
}

function isAetna62323(virtualClaim: VirtualClaimDTO): boolean {
  const payerName =
    virtualClaim.checklist.payer_insurance.payer_name.value ?? virtualClaim.payer?.name ?? "";
  const procedureCode =
    virtualClaim.checklist.service.procedure_code.value ?? virtualClaim.procedure?.code ?? "";
  return (
    typeof payerName === "string" &&
    payerName.toLowerCase().includes("aetna") &&
    formatValue(procedureCode).trim() === "62323"
  );
}

function sectionCount(fields: ChecklistSectionField[]): number {
  return fields.filter((item) => item.field.status === "missing").length;
}

type VirtualClaimPanelProps = {
  virtualClaim: VirtualClaimDTO | null;
  isLoading: boolean;
  error: string | null;
};

export default function VirtualClaimPanel({
  virtualClaim,
  isLoading,
  error,
}: VirtualClaimPanelProps) {
  if (isLoading && !virtualClaim) {
    return (
      <aside className="rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          Virtual Claim
        </div>
        <div className="mt-3 text-sm text-slate-500 dark:text-slate-400">
          Loading virtual claim checklist...
        </div>
      </aside>
    );
  }

  if (!virtualClaim) {
    return (
      <aside className="rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          Virtual Claim
        </div>
        {error ? (
          <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : (
          <div className="mt-3 text-sm text-slate-500 dark:text-slate-400">
            Start chatting to build the virtual claim checklist. The panel updates when
            the backend returns virtual claim state.
          </div>
        )}
      </aside>
    );
  }

  const patientFields = toFields([
    ["patient_id", "Patient ID", virtualClaim.checklist.patient.patient_id],
    ["first_name", "First name", virtualClaim.checklist.patient.first_name],
    ["last_name", "Last name", virtualClaim.checklist.patient.last_name],
    ["date_of_birth", "Date of birth", virtualClaim.checklist.patient.date_of_birth],
  ]);

  const payerFields = toFields([
    [
      "insurance_company_id",
      "Insurance company ID",
      virtualClaim.checklist.payer_insurance.insurance_company_id,
    ],
    ["payer_name", "Payer name", virtualClaim.checklist.payer_insurance.payer_name],
    ["member_id", "Member ID", virtualClaim.checklist.payer_insurance.member_id],
    ["group_number", "Group number", virtualClaim.checklist.payer_insurance.group_number],
    ["policy_number", "Policy number", virtualClaim.checklist.payer_insurance.policy_number],
  ]);

  const serviceFields = toFields([
    ["procedure_code", "CPT / procedure code", virtualClaim.checklist.service.procedure_code],
    [
      "procedure_description",
      "Procedure description",
      virtualClaim.checklist.service.procedure_description,
    ],
    ["service_date", "Service date", virtualClaim.checklist.service.service_date],
    [
      "rendering_provider",
      "Rendering provider",
      virtualClaim.checklist.service.rendering_provider,
    ],
    ["quantity", "Quantity", virtualClaim.checklist.service.quantity],
    ["modifier", "Modifier", virtualClaim.checklist.service.modifier],
  ]);

  const diagnosisFields = toFields([
    ["diagnosis_code", "Diagnosis code", virtualClaim.checklist.diagnosis.diagnosis_code],
    [
      "diagnosis_description",
      "Diagnosis description",
      virtualClaim.checklist.diagnosis.diagnosis_description,
    ],
  ]);

  const payerKnown =
    virtualClaim.checklist.payer_insurance.payer_name.status !== "missing" ||
    virtualClaim.checklist.payer_insurance.insurance_company_id.status !== "missing";
  const procedureKnown = virtualClaim.checklist.service.procedure_code.status !== "missing";
  const showMedicalNecessity = payerKnown && procedureKnown;

  const medicalNecessityFields = toFields([
    ["policy_link_id", "Policy link ID", virtualClaim.checklist.policy_medical_necessity.policy_link_id],
    ["policy_url", "Policy URL", virtualClaim.checklist.policy_medical_necessity.policy_url],
    [
      "stored_rules_available",
      "Stored rules available",
      virtualClaim.checklist.policy_medical_necessity.stored_rules_available,
    ],
    [
      "radiculopathy_evidence",
      "Lumbar / radicular symptoms",
      virtualClaim.checklist.policy_medical_necessity.radiculopathy_evidence,
    ],
    [
      "dermatomal_distribution",
      "Dermatomal distribution",
      virtualClaim.checklist.policy_medical_necessity.dermatomal_distribution,
    ],
    [
      "functional_limitation",
      "Functional limitation",
      virtualClaim.checklist.policy_medical_necessity.functional_limitation,
    ],
    [
      "conservative_treatment_failed",
      "Failed conservative treatment",
      virtualClaim.checklist.policy_medical_necessity.conservative_treatment_failed,
    ],
    [
      "imaging_guidance",
      "Imaging guidance fluoroscopy / CT",
      virtualClaim.checklist.policy_medical_necessity.imaging_guidance,
    ],
    [
      "mri_or_ct_or_emg",
      "MRI / CT or EMG evidence",
      virtualClaim.checklist.policy_medical_necessity.MRI_or_CT_or_EMG_evidence,
    ],
    [
      "neuro_exam_evidence",
      "Neuro exam evidence",
      virtualClaim.checklist.policy_medical_necessity.neuro_exam_evidence,
    ],
    [
      "frequency_session_limits_respected",
      "Session / frequency limits",
      virtualClaim.checklist.policy_medical_necessity.frequency_session_limits_respected,
    ],
    [
      "vertebral_level_limits_respected",
      "Level limits",
      virtualClaim.checklist.policy_medical_necessity.vertebral_level_limits_respected,
    ],
  ]);

  const cheatSheetFields = toFields([
    [
      "aetna_62323_radicular",
      "Lumbar / radicular symptoms",
      virtualClaim.checklist.policy_medical_necessity.radiculopathy_evidence,
    ],
    [
      "aetna_62323_dermatomal",
      "Dermatomal distribution",
      virtualClaim.checklist.policy_medical_necessity.dermatomal_distribution,
    ],
    [
      "aetna_62323_functional",
      "Functional limitation",
      virtualClaim.checklist.policy_medical_necessity.functional_limitation,
    ],
    [
      "aetna_62323_conservative",
      "Failed conservative treatment",
      virtualClaim.checklist.policy_medical_necessity.conservative_treatment_failed,
    ],
    [
      "aetna_62323_guidance",
      "Imaging guidance fluoroscopy / CT",
      virtualClaim.checklist.policy_medical_necessity.imaging_guidance,
    ],
    [
      "aetna_62323_imaging",
      "MRI / CT or EMG evidence",
      virtualClaim.checklist.policy_medical_necessity.MRI_or_CT_or_EMG_evidence,
    ],
    [
      "aetna_62323_neuro_exam",
      "Neuro exam evidence",
      virtualClaim.checklist.policy_medical_necessity.neuro_exam_evidence,
    ],
    [
      "aetna_62323_limits",
      "Session / frequency / level limits",
      virtualClaim.checklist.policy_medical_necessity.frequency_session_limits_respected,
    ],
  ]);

  const missingCount = virtualClaim.checklist.readiness.missing_fields.length;
  const suggestedQuestions = virtualClaim.checklist.readiness.next_questions;

  return (
    <aside className="flex min-h-[480px] min-h-0 flex-col gap-4 overflow-y-auto rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Virtual Claim
          </div>
          <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Live checklist state from the current chat session
          </div>
        </div>
        <ReadinessBadge ready={virtualClaim.checklist.readiness.ready_to_draft} />
      </div>

      <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950">
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              Patient
            </div>
            <div className="mt-1 font-medium text-slate-900 dark:text-slate-100">
              {virtualClaim.patient?.name ?? "—"}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              Payer
            </div>
            <div className="mt-1 font-medium text-slate-900 dark:text-slate-100">
              {virtualClaim.payer?.name ?? "—"}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              CPT
            </div>
            <div className="mt-1 font-medium text-slate-900 dark:text-slate-100">
              {virtualClaim.procedure?.code ?? "—"}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              Updated
            </div>
            <div className="mt-1 font-medium text-slate-900 dark:text-slate-100">
              {formatDate(virtualClaim.updated_at)}
            </div>
          </div>
        </div>
        {virtualClaim.readiness_reason ? (
          <div className="mt-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            {virtualClaim.readiness_reason}
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          {error}
        </div>
      ) : null}

      <ChecklistSection title="Patient" fields={patientFields} />
      <ChecklistSection title="Payer / Insurance" fields={payerFields} />
      <ChecklistSection title="Service" fields={serviceFields} />
      <ChecklistSection title="Diagnosis" fields={diagnosisFields} />

      {showMedicalNecessity ? (
        <>
          <ChecklistSection
            title="Medical Necessity"
            fields={medicalNecessityFields}
            emptyLabel="No medical necessity checklist available yet."
          />
          {isAetna62323(virtualClaim) ? (
            <section className="space-y-3 rounded-3xl border border-sky-200 bg-sky-50 p-4 dark:border-sky-500/30 dark:bg-sky-500/10">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700 dark:text-sky-300">
                  Aetna 62323 Policy Cheat-Sheet
                </div>
                <div className="mt-1 text-sm text-sky-900 dark:text-sky-100">
                  Quick checklist for the current payer + CPT combination.
                </div>
              </div>
              <div className="space-y-2">
                {cheatSheetFields.map((item) => (
                  <div
                    key={item.key}
                    className={cn(
                      "rounded-2xl border px-3 py-2 text-sm",
                      item.field.status === "missing"
                        ? "border-rose-200 bg-white text-rose-800 dark:border-rose-500/30 dark:bg-slate-900 dark:text-rose-200"
                        : "border-emerald-200 bg-white text-slate-700 dark:border-emerald-500/30 dark:bg-slate-900 dark:text-slate-100"
                    )}
                  >
                    <div className="font-medium">{item.label}</div>
                    <div className="mt-1 text-xs opacity-80">{formatValue(item.field.value)}</div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : (
        <section className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
          <div className="text-xs font-semibold uppercase tracking-[0.18em]">
            Medical Necessity
          </div>
          <div className="mt-2">
            This checklist appears once payer and CPT code are known.
          </div>
        </section>
      )}

      <section className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              Readiness
            </div>
            <div className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Missing required fields: {missingCount}
            </div>
          </div>
          <ReadinessBadge ready={virtualClaim.checklist.readiness.ready_to_draft} />
        </div>

        <div className="grid gap-3">
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-900">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
              Blocking reasons
            </div>
            {virtualClaim.checklist.readiness.blocking_reasons.length === 0 ? (
              <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                No blockers.
              </div>
            ) : (
              <ul className="mt-2 space-y-2 text-sm text-slate-700 dark:text-slate-200">
                {virtualClaim.checklist.readiness.blocking_reasons.map((reason) => (
                  <li key={reason} className="list-inside list-disc">
                    {reason}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-900">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
              Suggested next questions
            </div>
            {suggestedQuestions.length === 0 ? (
              <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                No follow-up questions suggested.
              </div>
            ) : (
              <ul className="mt-2 space-y-2 text-sm text-slate-700 dark:text-slate-200">
                {suggestedQuestions.map((question) => (
                  <li key={question} className="list-inside list-disc">
                    {question}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
        Filled fields:{" "}
        {patientFields.length + payerFields.length + serviceFields.length + diagnosisFields.length + medicalNecessityFields.length - (
          sectionCount(patientFields) +
          sectionCount(payerFields) +
          sectionCount(serviceFields) +
          sectionCount(diagnosisFields) +
          sectionCount(medicalNecessityFields)
        )}{" "}
        · Missing fields:{" "}
        {sectionCount(patientFields) +
          sectionCount(payerFields) +
          sectionCount(serviceFields) +
          sectionCount(diagnosisFields) +
          sectionCount(medicalNecessityFields)}
      </div>
    </aside>
  );
}
