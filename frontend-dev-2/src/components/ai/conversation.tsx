import { Message, MessageProps } from "@/components/ai/message";

export interface ConversationProps {
  messages: MessageProps[];
  emptyState?: string;
}

export function Conversation({ messages, emptyState }: ConversationProps) {
  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        {emptyState ?? "No messages yet."}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {messages.map((message, index) => (
        <div
          key={`${message.role}-${index}`}
          className={message.role === "user" ? "items-end" : "items-start"}
        >
          <Message {...message} />
        </div>
      ))}
    </div>
  );
}
