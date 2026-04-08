import { z } from "zod";

import { requestJson } from "@/lib/api/client";
import type { MeDTO, UserRole } from "@/types/auth";

const tokenSchema = z.object({
  access_token: z.string(),
  token_type: z.string().optional().default("bearer"),
});

const meSchema = z.object({
  id: z.number(),
  email: z.string(),
  full_name: z.string().nullable().optional(),
  role: z.enum(["doctor", "chief_doctor", "clinic_admin", "platform_staff_admin"]),
  clinic_id: z.number(),
  clinic_name: z.string().nullable().optional(),
  is_active: z.boolean(),
});

export type LoginResponse = z.infer<typeof tokenSchema>;

function toMe(dto: z.infer<typeof meSchema>): MeDTO {
  return {
    id: dto.id,
    email: dto.email,
    full_name: dto.full_name ?? undefined,
    role: dto.role as UserRole,
    clinic_id: dto.clinic_id,
    clinic_name: dto.clinic_name ?? undefined,
    is_active: dto.is_active,
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

export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await requestJson<unknown>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return parseWithSchema(tokenSchema, data, "login");
}

export async function getMe(): Promise<MeDTO> {
  const data = await requestJson<unknown>("/auth/me");
  const parsed = parseWithSchema(meSchema, data, "me");
  return toMe(parsed);
}
