import type { VirtualClaimDTO } from "@/types/virtualClaim";

export type ID = number;

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface DevTokenRequest {
  user_id: ID;
}

export interface AdminCreateUserRequest {
  email: string;
  full_name?: string | null;
  password: string;
  roles?: string[] | null;
}

export interface AdminCreateUserResponse {
  access_token: string;
  token_type: "bearer";
  user_id: ID;
  email: string;
  roles: string[];
}

export interface UserResponse {
  id: ID;
  email: string;
  full_name?: string | null;
  role: string;
  clinic_id: ID;
  clinic_name?: string | null;
  is_active: boolean;
}

export interface ChatRequest {
  message: string;
  session_id?: ID | null;
  metadata?: Record<string, unknown> | null;
}

export interface ChatResponse {
  session_id: ID;
  assistant_message: string;
  ui_actions: Record<string, unknown>[];
  debug?: Record<string, unknown> | null;
  action_required: boolean;
  proposed_changes?: Record<string, unknown> | null;
  virtual_claim?: VirtualClaimDTO | null;
}

export interface ChatSessionCreateRequest {
  title?: string | null;
}

export interface ChatSessionResponse {
  id: ID;
  doctor_id: ID;
  created_at: string | null;
  title?: string | null;
}

export interface ChatMessageResponse {
  id: ID;
  role: string;
  content: string;
  created_at: string | null;
}

export interface HealthResponse {
  status: string;
}

export interface StatusResponse {
  db_ready: boolean;
  llm_ready: boolean | null;
  overall_ready: boolean;
  reason: string | null;
  checked_at: string;
  env: string;
  llm_model: string;
  lmstudio_base_url: string;
  llm_max_steps: number;
}

export interface RootResponse {
  service: string;
  status: string;
}
