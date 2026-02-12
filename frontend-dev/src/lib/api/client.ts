import { ApiError, isApiErrorPayload } from "@/lib/api/errors";
import { getStoredToken } from "@/lib/auth/token";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
let lastRequestId: string | null = null;

export function getLastRequestId(): string | null {
  return lastRequestId;
}

function setLastRequestId(value: string | null): void {
  lastRequestId = value;
}

function buildUrl(path: string): string {
  if (!API_BASE_URL) {
    return path;
  }
  return new URL(path, API_BASE_URL).toString();
}

export function apiUrl(path: string): string {
  return buildUrl(path);
}

function createRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  const random = Math.random().toString(16).slice(2, 10);
  return `req_${Date.now()}_${random}`;
}

async function safeParseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function buildHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const token = getStoredToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token.accessToken}`);
  }
  headers.set("X-Request-ID", createRequestId());
  return headers;
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: buildHeaders(init.headers),
  });
  const data = await safeParseJson(response);
  const requestId = response.headers.get("X-Request-ID");
  setLastRequestId(requestId);

  if (!response.ok) {
    const payload = isApiErrorPayload(data) ? data : null;
    throw new ApiError(response.status, payload, requestId);
  }

  if (data === null) {
    throw new ApiError(response.status, null, requestId);
  }

  return data as T;
}

export async function requestVoid(path: string, init: RequestInit = {}): Promise<void> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: buildHeaders(init.headers),
  });
  const requestId = response.headers.get("X-Request-ID");
  setLastRequestId(requestId);

  if (!response.ok) {
    const data = await safeParseJson(response);
    const payload = isApiErrorPayload(data) ? data : null;
    throw new ApiError(response.status, payload, requestId);
  }
}
