import { z } from "zod";

import { requestJson, requestVoid } from "@/lib/api/client";

const chatSessionSchema = z.object({
  id: z.number(),
  doctor_id: z.number(),
  created_at: z.string().nullable(),
  title: z.string().nullable().optional(),
});

const chatSessionsSchema = z.array(chatSessionSchema);

const chatMessageSchema = z.object({
  id: z.number(),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  created_at: z.string().nullable(),
});

const chatMessagesSchema = z.array(chatMessageSchema);

const chatResponseSchema = z.object({
  session_id: z.number(),
  assistant_message: z.string(),
  ui_actions: z.array(z.record(z.string(), z.unknown())),
  debug: z.record(z.string(), z.unknown()).nullable().optional(),
  action_required: z.boolean(),
  proposed_changes: z.record(z.string(), z.unknown()).nullable().optional(),
});

export type ChatSession = z.infer<typeof chatSessionSchema>;
export type ChatMessage = z.infer<typeof chatMessageSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;

export interface SendChatInput {
  session_id: number;
  message: string;
  metadata?: {
    client_message_id?: string;
  };
}

function parseWithSchema<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((issue) => issue.message).join("; ");
    throw new Error(`Invalid ${label} response: ${issues}`);
  }
  return parsed.data;
}

export async function listSessions(): Promise<ChatSession[]> {
  const data = await requestJson<unknown>("/api/chat/sessions");
  return parseWithSchema(chatSessionsSchema, data, "list sessions");
}

export async function createSession(title?: string): Promise<ChatSession> {
  const data = await requestJson<unknown>("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title ?? null }),
  });
  return parseWithSchema(chatSessionSchema, data, "create session");
}

export async function deleteSession(id: number): Promise<void> {
  await requestVoid(`/api/chat/sessions/${id}`, { method: "DELETE" });
}

export async function listMessages(sessionId: number): Promise<ChatMessage[]> {
  const data = await requestJson<unknown>(`/api/chat/sessions/${sessionId}/messages`);
  return parseWithSchema(chatMessagesSchema, data, "list messages");
}

export async function sendChatMessage(input: SendChatInput): Promise<ChatResponse> {
  const data = await requestJson<unknown>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseWithSchema(chatResponseSchema, data, "send chat");
}
