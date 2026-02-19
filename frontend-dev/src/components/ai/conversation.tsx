import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

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

  const parentRef = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 120,
    overscan: 8,
  });

  return (
    <div ref={parentRef} className="h-full overflow-auto">
      <div
        className="relative w-full"
        style={{ height: `${virtualizer.getTotalSize()}px` }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const message = messages[virtualRow.index];
          return (
            <div
              key={`${message.role}-${virtualRow.index}`}
              className={`flex py-2 ${message.role === "user" ? "justify-end" : "justify-start"}`}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
              }}
              ref={virtualizer.measureElement}
              data-index={virtualRow.index}
            >
              <Message {...message} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
