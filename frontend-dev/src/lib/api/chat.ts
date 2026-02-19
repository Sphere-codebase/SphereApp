import { z } from "zod";

import { requestJson, requestVoid } from "@/lib/api/client";

const chatSessionSchema = z.object({
  id: z.number(),
  doctor_id: z.number(),
  created_at: z.string().nullable(),
  claim_id: z.number().nullable().optional(),
  patient_id: z.number().nullable().optional(),
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

const chatConfirmResponseSchema = z.object({
  status: z.enum(["confirmed", "rejected"]),
  result: z.record(z.string(), z.unknown()).nullable().optional(),
});

export type ChatSession = z.infer<typeof chatSessionSchema>;
export type ChatMessage = z.infer<typeof chatMessageSchema>;
export type ChatResponse = z.infer<typeof chatResponseSchema>;
export type ChatConfirmResponse = z.infer<typeof chatConfirmResponseSchema>;

export interface SendChatInput {
  session_id: number;
  message: string;
  metadata?: {
    client_message_id?: string;
  };
}

export interface ConfirmChatActionInput {
  session_id: number;
  proposal_id?: string | null;
  decision: "confirm" | "reject";
  tool: string;
  arguments?: Record<string, unknown>;
  payload?: Record<string, unknown> | null;
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

export async function createSession(
  title?: string,
  claimId?: number | null
): Promise<ChatSession> {
  const data = await requestJson<unknown>("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title ?? null, claim_id: claimId ?? null }),
  });
  return parseWithSchema(chatSessionSchema, data, "create session");
}

export async function updateSession(
  sessionId: number,
  payload: { title?: string | null; claim_id?: number | null }
): Promise<ChatSession> {
  const data = await requestJson<unknown>(`/api/chat/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseWithSchema(chatSessionSchema, data, "update session");
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

export async function confirmChatAction(
  input: ConfirmChatActionInput
): Promise<ChatConfirmResponse> {
  const data = await requestJson<unknown>("/api/chat/confirm-action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: input.session_id,
      proposal_id: input.proposal_id ?? null,
      decision: input.decision,
      tool: input.tool,
      arguments: input.arguments ?? {},
      payload: input.payload ?? null,
    }),
  });
  return parseWithSchema(chatConfirmResponseSchema, data, "confirm chat action");
}
