import ChecklistSection, {
  type ChecklistSectionField,
} from "@/components/workspace/ChecklistSection";
import ReadinessBadge from "@/components/workspace/ReadinessBadge";
import { cn } from "@/lib/utils";
import type {
  VirtualClaimChecklistValueDTO,
  VirtualClaimDTO,
} from "@/types/virtualClaim";

const FIELD_LABELS: Record<string, string> = {
  patient_id: "Patient",
  insurance_company_id: "Payer",
  procedure_code: "CPT",
  service_date: "Service date",
  "service.service_date": "Service date",
  "service.procedure_code": "CPT",
  "diagnosis.code": "Diagnosis code",
  "diagnosis.description": "Diagnosis description",
  "clinical.radiculopathy": "Radiculopathy symptoms",
  "clinical.functional_limitation": "Functional limitation",
  "clinical.conservative_treatment": "Failed conservative treatment",
  "clinical.imaging_guidance": "Imaging guidance",
  "clinical.radiology_consistency": "Radiology findings",
  "clinical.neuro_exam": "Neuro exam evidence",
  "clinical.mri_or_emg": "MRI / CT / EMG evidence",
  "treatment.initial_tfesi": "Initial therapeutic TFESI",
  "utilization.level_limit_ok": "Vertebral level limits",
  "utilization.frequency_limit_ok": "Frequency / session limits",
  "policy.link": "Stored payer policy link",
  "policy.rule": "Stored payer policy rules",
  "patient.patient_id": "Patient",
  "payer_insurance.insurance_company_id": "Payer",
  "service.procedure_description": "Procedure description",
  "policy_medical_necessity.radiculopathy_evidence": "Radiculopathy symptoms",
  "policy_medical_necessity.dermatomal_distribution": "Dermatomal distribution",
  "policy_medical_necessity.functional_limitation": "Functional limitation",
  "policy_medical_necessity.conservative_treatment_failed":
    "Failed conservative treatment",
  "policy_medical_necessity.imaging_guidance": "Imaging guidance",
  "policy_medical_necessity.MRI_or_CT_or_EMG_evidence": "MRI / CT / EMG evidence",
  "policy_medical_necessity.neuro_exam_evidence": "Neuro exam evidence",
  "policy_medical_necessity.frequency_session_limits_respected":
    "Frequency / session limits",
  "policy_medical_necessity.vertebral_level_limits_respected": "Vertebral level limits",
  "policy_medical_necessity.radiologic_findings_consistent":
    "Radiology findings consistent with symptoms",
};

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

function formatChecklistValue(key: string, value: unknown): string {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }
  if (key === "procedure_code" && typeof value === "string" && value.trim()) {
    return value.trim();
  }
  return formatValue(value);
}

function patientName(virtualClaim: VirtualClaimDTO): string {
  const firstName = virtualClaim.checklist.patient.first_name.value;
  const lastName = virtualClaim.checklist.patient.last_name.value;
  const composed = [firstName, lastName]
    .filter((part): part is string => typeof part === "string" && part.trim().length > 0)
    .join(" ");
  const resolvedName = virtualClaim.patient?.name ?? composed;
  return resolvedName || "—";
}

function labelForKey(key: string): string {
  return FIELD_LABELS[key] ?? key;
}

function humanizeText(value: string): string {
  let rendered = value;
  const replacements = Object.entries(FIELD_LABELS).sort(
    ([left], [right]) => right.length - left.length
  );
  for (const [key, label] of replacements) {
    rendered = rendered.split(key).join(label);
  }
  return rendered;
}

function toFields(
  entries: Array<
    [key: string, label: string, field: VirtualClaimChecklistValueDTO | null | undefined]
  >
): ChecklistSectionField[] {
  return entries
    .filter(([, , field]) => Boolean(field))
    .map(([key, label, field]) => ({
      key,
      label,
      field: field as VirtualClaimChecklistValueDTO,
    }));
}

function synthesizeField(
  baseField: VirtualClaimChecklistValueDTO,
  value: unknown,
  label: string
): VirtualClaimChecklistValueDTO {
  return {
    ...baseField,
    label,
    value,
  };
}

function isAetna62323(virtualClaim: VirtualClaimDTO): boolean {
  const payerName =
    virtualClaim.checklist.payer_insurance.payer_name.value ??
    virtualClaim.payer?.name ??
    "";
  const procedureCode =
    virtualClaim.checklist.service.procedure_code.value ??
    virtualClaim.procedure?.code ??
    "";
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
    [
      "patient_name",
      "Patient",
      synthesizeField(
        virtualClaim.checklist.patient.patient_id,
        patientName(virtualClaim),
        "Patient"
      ),
    ],
    ["date_of_birth", "DOB", virtualClaim.checklist.patient.date_of_birth],
  ]);

  const payerFields = toFields([
    ["payer_name", "Payer", virtualClaim.checklist.payer_insurance.payer_name],
    ["member_id", "Member ID", virtualClaim.checklist.payer_insurance.member_id],
    ["group_number", "Group number", virtualClaim.checklist.payer_insurance.group_number],
    [
      "policy_number",
      "Policy number",
      virtualClaim.checklist.payer_insurance.policy_number,
    ],
  ]);

  const serviceFields = toFields([
    ["procedure_code", "CPT", virtualClaim.checklist.service.procedure_code],
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
  const procedureKnown =
    virtualClaim.checklist.service.procedure_code.status !== "missing";
  const showMedicalNecessity = payerKnown && procedureKnown;

  const medicalNecessityFields = toFields([
    [
      "radiculopathy_evidence",
      "Radiculopathy symptoms",
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
      "Imaging guidance",
      virtualClaim.checklist.policy_medical_necessity.imaging_guidance,
    ],
    [
      "mri_or_ct_or_emg",
      "MRI / CT / EMG evidence",
      virtualClaim.checklist.policy_medical_necessity.MRI_or_CT_or_EMG_evidence,
    ],
    [
      "neuro_exam_evidence",
      "Neuro exam evidence",
      virtualClaim.checklist.policy_medical_necessity.neuro_exam_evidence,
    ],
    [
      "frequency_session_limits_respected",
      "Frequency / session limits",
      virtualClaim.checklist.policy_medical_necessity.frequency_session_limits_respected,
    ],
    [
      "vertebral_level_limits_respected",
      "Vertebral level limits",
      virtualClaim.checklist.policy_medical_necessity.vertebral_level_limits_respected,
    ],
  ]);

  const cheatSheetFields = toFields([
    [
      "aetna_62323_radicular",
      "Radiculopathy symptoms",
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
      "Imaging guidance",
      virtualClaim.checklist.policy_medical_necessity.imaging_guidance,
    ],
    [
      "aetna_62323_imaging",
      "MRI / CT / EMG evidence",
      virtualClaim.checklist.policy_medical_necessity.MRI_or_CT_or_EMG_evidence,
    ],
    [
      "aetna_62323_neuro_exam",
      "Neuro exam evidence",
      virtualClaim.checklist.policy_medical_necessity.neuro_exam_evidence,
    ],
    [
      "aetna_62323_limits",
      "Frequency / session / level limits",
      virtualClaim.checklist.policy_medical_necessity.frequency_session_limits_respected,
    ],
  ]);

  const missingCount = virtualClaim.checklist.readiness.missing_fields.length;
  const suggestedQuestions =
    virtualClaim.follow_up_questions.length > 0
      ? virtualClaim.follow_up_questions
          .slice(0, 3)
          .map((item) => humanizeText(item.prompt))
      : virtualClaim.checklist.readiness.next_questions
          .slice(0, 3)
          .map((item) => humanizeText(item));
  const blockingReasons =
    virtualClaim.checklist.readiness.blocking_reasons.length > 0
      ? virtualClaim.checklist.readiness.blocking_reasons.map((item) =>
          humanizeText(item)
        )
      : virtualClaim.checklist.readiness.missing_fields.map(
          (item) => `Missing: ${labelForKey(item)}`
        );
  const technicalDetails = [
    ["draft_id", String(virtualClaim.draft_id)],
    ["session_id", String(virtualClaim.session_id)],
    ["materialized_claim_id", String(virtualClaim.materialized_claim_id ?? "—")],
    ["patient_id", String(virtualClaim.patient?.id ?? "—")],
    ["insurance_company_id", String(virtualClaim.payer?.id ?? "—")],
    ["procedure_code", String(virtualClaim.procedure?.code ?? "—")],
    ["policy_link_id", String(virtualClaim.policy_summary?.policy_link_id ?? "—")],
    ["policy_rule_id", String(virtualClaim.policy_summary?.policy_rule_id ?? "—")],
    ["policy_url", String(virtualClaim.policy_summary?.policy_url ?? "—")],
    [
      "missing_field_keys",
      virtualClaim.checklist.readiness.missing_fields.length > 0
        ? virtualClaim.checklist.readiness.missing_fields.join(", ")
        : "—",
    ],
  ];

  return (
    <aside className="flex min-h-[480px] min-h-0 flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
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
      <div className="flex-1 overflow-y-auto px-4 gap-4 flex flex-col">
        <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-wrap gap-2 text-sm">
            <div className="rounded-full bg-white px-3 py-2 font-medium text-slate-900 dark:bg-slate-900 dark:text-slate-100">
              Patient: {patientName(virtualClaim)}
            </div>
            <div className="rounded-full bg-white px-3 py-2 font-medium text-slate-900 dark:bg-slate-900 dark:text-slate-100">
              DOB:{" "}
              {formatChecklistValue(
                "date_of_birth",
                virtualClaim.checklist.patient.date_of_birth.value
              )}
            </div>
            <div className="rounded-full bg-white px-3 py-2 font-medium text-slate-900 dark:bg-slate-900 dark:text-slate-100">
              Payer:{" "}
              {formatChecklistValue(
                "payer_name",
                virtualClaim.checklist.payer_insurance.payer_name.value
              )}
            </div>
            <div className="rounded-full bg-white px-3 py-2 font-medium text-slate-900 dark:bg-slate-900 dark:text-slate-100">
              CPT{" "}
              {formatChecklistValue(
                "procedure_code",
                virtualClaim.checklist.service.procedure_code.value
              )}
            </div>
            <div className="rounded-full bg-white px-3 py-2 font-medium text-slate-900 dark:bg-slate-900 dark:text-slate-100">
              Service date:{" "}
              {formatChecklistValue(
                "service_date",
                virtualClaim.checklist.service.service_date.value
              )}
            </div>
            <div className="rounded-full bg-white px-3 py-2 font-medium text-slate-900 dark:bg-slate-900 dark:text-slate-100">
              Updated: {formatDate(virtualClaim.updated_at)}
            </div>
          </div>
          {virtualClaim.readiness_reason ? (
            <div className="mt-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
              {humanizeText(virtualClaim.readiness_reason)}
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
                      <div className="mt-1 text-xs opacity-80">
                        {formatChecklistValue(item.key, item.field.value)}
                      </div>
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
            <div className="min-w-0 w-full rounded-2xl border border-slate-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-slate-900">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                Blocking reasons
              </div>
              {blockingReasons.length === 0 ? (
                <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                  No blockers.
                </div>
              ) : (
                <ul className="mt-2 space-y-2 text-sm text-slate-700 dark:text-slate-200 break-words overflow-hidden">
                  {blockingReasons.map((reason) => (
                    <li key={reason} className="flex gap-2">
                      <span className="shrink-0">•</span>
                      <span className="min-w-0 flex-1">{reason}</span>
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
          {patientFields.length +
            payerFields.length +
            serviceFields.length +
            diagnosisFields.length +
            medicalNecessityFields.length -
            (sectionCount(patientFields) +
              sectionCount(payerFields) +
              sectionCount(serviceFields) +
              sectionCount(diagnosisFields) +
              sectionCount(medicalNecessityFields))}{" "}
          · Missing fields:{" "}
          {sectionCount(patientFields) +
            sectionCount(payerFields) +
            sectionCount(serviceFields) +
            sectionCount(diagnosisFields) +
            sectionCount(medicalNecessityFields)}
        </div>

        <details className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
          <summary className="cursor-pointer select-none font-semibold text-slate-700 dark:text-slate-200">
            Technical details
          </summary>
          <div className="mt-3 space-y-2">
            {technicalDetails.map(([label, value]) => (
              <div key={label} className="break-all">
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  {label}
                </span>
                : {value}
              </div>
            ))}
          </div>
        </details>
      </div>
    </aside>
  );
}
