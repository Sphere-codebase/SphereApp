import ChecklistField from "@/components/workspace/ChecklistField";
import type { VirtualClaimChecklistValueDTO } from "@/types/virtualClaim";

export type ChecklistSectionField = {
  key: string;
  label: string;
  field: VirtualClaimChecklistValueDTO;
};

type ChecklistSectionProps = {
  title: string;
  fields: ChecklistSectionField[];
  emptyLabel?: string;
};

export default function ChecklistSection({
  title,
  fields,
  emptyLabel = "No checklist fields available yet.",
}: ChecklistSectionProps) {
  return (
    <section className="space-y-3 rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
        {title}
      </div>
      {fields.length === 0 ? (
        <div className="text-sm text-slate-500 dark:text-slate-400">{emptyLabel}</div>
      ) : (
        <div className="space-y-2">
          {fields.map((item) => (
            <ChecklistField key={item.key} label={item.label} field={item.field} />
          ))}
        </div>
      )}
    </section>
  );
}
