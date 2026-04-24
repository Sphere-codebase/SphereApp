import { cn } from "@/lib/utils";

type ReadinessBadgeProps = {
  ready: boolean;
};

export default function ReadinessBadge({ ready }: ReadinessBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]",
        ready
          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200"
          : "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200"
      )}
    >
      Ready to draft: {ready ? "YES" : "NO"}
    </span>
  );
}
