export type MessageRole = "user" | "assistant" | "system";

export interface MessageProps {
  role: MessageRole;
  content: string;
  timestamp?: string;
}

const roleStyles: Record<MessageRole, string> = {
  user: "bg-slate-900 text-white dark:bg-slate-700",
  assistant: "bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100",
  system: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
};

export function Message({ role, content, timestamp }: MessageProps) {
  const isUser = role === "user";
  const isMultiline = content.includes("\n");

  return (
    <div className={`flex w-full flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
      <div
        className={`inline-block max-w-[75%] rounded-2xl px-4 py-3 shadow-sm ${roleStyles[role]}`}
      >
        <p
          className={[
            "text-sm leading-relaxed text-left break-words",
            isMultiline ? "whitespace-pre-wrap" : "whitespace-normal",
          ].join(" ")}
        >
          {content}
        </p>
      </div>

      {timestamp ? <span className="text-xs text-slate-500">{timestamp}</span> : null}
    </div>
  );
}