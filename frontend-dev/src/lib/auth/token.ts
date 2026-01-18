export interface StoredToken {
  accessToken: string;
  tokenType: "bearer";
}

const TOKEN_KEY = "sphereapp_token";
const LOGOUT_FLAG_KEY = "sphereapp_logged_out";

export function getStoredToken(): StoredToken | null {
  const raw = localStorage.getItem(TOKEN_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const record = parsed as Record<string, unknown>;
    if (typeof record.accessToken !== "string" || record.tokenType !== "bearer") {
      return null;
    }
    return { accessToken: record.accessToken, tokenType: "bearer" };
  } catch {
    return null;
  }
}

export function setStoredToken(token: StoredToken): void {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(token));
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isLogoutFlagSet(): boolean {
  return sessionStorage.getItem(LOGOUT_FLAG_KEY) === "1";
}

export function setLogoutFlag(): void {
  sessionStorage.setItem(LOGOUT_FLAG_KEY, "1");
}

export function clearLogoutFlag(): void {
  sessionStorage.removeItem(LOGOUT_FLAG_KEY);
}
