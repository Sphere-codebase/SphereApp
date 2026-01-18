export interface ApiErrorDetail {
  code: string;
  message: string;
  details: unknown;
}

export interface ApiErrorPayload {
  error: ApiErrorDetail;
}

export class ApiError extends Error {
  readonly status: number;
  readonly payload: ApiErrorPayload | null;
  readonly requestId: string | null;

  constructor(status: number, payload: ApiErrorPayload | null, requestId: string | null) {
    super(payload?.error.message ?? "API request failed");
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
    this.requestId = requestId;
  }
}

export function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (!value || typeof value !== "object") {
    return false;
  }
  const record = value as Record<string, unknown>;
  if (!("error" in record)) {
    return false;
  }
  const errorValue = record.error;
  if (!errorValue || typeof errorValue !== "object") {
    return false;
  }
  const errorRecord = errorValue as Record<string, unknown>;
  return (
    typeof errorRecord.code === "string" &&
    typeof errorRecord.message === "string" &&
    "details" in errorRecord
  );
}
