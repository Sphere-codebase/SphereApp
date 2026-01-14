import { Button } from "@/components/ui/button";

export interface PromptInputProps {
  value: string;
  placeholder?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function PromptInput({
  value,
  placeholder,
  disabled = false,
  onChange,
  onSubmit,
}: PromptInputProps) {
  return (
    <div className="flex gap-3">
      <textarea
        className="min-h-[52px] flex-1 resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:focus:ring-slate-600"
        placeholder={placeholder ?? "Send a message..."}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      />
      <Button type="button" onClick={onSubmit} disabled={disabled}>
        Send
      </Button>
    </div>
  );
}
