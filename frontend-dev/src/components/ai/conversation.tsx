import { useCallback, useEffect, useRef } from "react";

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
  const stickToBottomRef = useRef(true);
  const lastMessageCountRef = useRef(0);
  const SCROLL_THRESHOLD_PX = 64;

  const updateStickiness = useCallback(() => {
    const container = parentRef.current;
    if (!container) {
      return;
    }
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    stickToBottomRef.current = distanceFromBottom <= SCROLL_THRESHOLD_PX;
  }, []);

  const scrollToBottom = useCallback(() => {
    const container = parentRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
    updateStickiness();
  }, [updateStickiness]);

  useEffect(() => {
    updateStickiness();
  }, [updateStickiness]);

  useEffect(() => {
    const previousCount = lastMessageCountRef.current;
    const currentCount = messages.length;
    const isReset = currentCount < previousCount;
    lastMessageCountRef.current = currentCount;

    if (stickToBottomRef.current || isReset) {
      requestAnimationFrame(scrollToBottom);
    }
  }, [messages, scrollToBottom]);

  return (
    <div ref={parentRef} className="h-full overflow-auto" onScroll={updateStickiness}>
      <div className="flex w-full flex-col">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`flex py-2 ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <Message {...message} />
          </div>
        ))}
      </div>
    </div>
  );
}
