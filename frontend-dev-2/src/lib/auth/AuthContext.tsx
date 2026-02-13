import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { requestJson } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type {
  AdminCreateUserRequest,
  AdminCreateUserResponse,
  LoginRequest,
  TokenResponse,
  UserResponse,
} from "@/lib/api/types";
import {
  clearLogoutFlag,
  getStoredToken,
  isLogoutFlagSet,
  setLogoutFlag,
  setStoredToken,
  type StoredToken,
} from "@/lib/auth/token";

export interface AuthContextValue {
  user: UserResponse | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  bootstrapCreateUser: (payload: AdminCreateUserRequest) => Promise<void>;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function getInitialToken(): string | null {
  if (isLogoutFlagSet()) {
    return null;
  }
  return getStoredToken()?.accessToken ?? null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(getInitialToken);
  const [isLoading, setIsLoading] = useState(false);

  const logout = useCallback(() => {
    setLogoutFlag();
    setToken(null);
    setUser(null);
  }, []);

  const refreshMe = useCallback(async () => {
    const storedToken = isLogoutFlagSet() ? null : getStoredToken()?.accessToken ?? null;
    const currentToken = token ?? storedToken ?? null;
    if (!currentToken) {
      setUser(null);
      return;
    }
    setIsLoading(true);
    try {
      const me = await requestJson<UserResponse>("/auth/me");
      setUser(me);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        logout();
      } else {
        throw error;
      }
    } finally {
      setIsLoading(false);
    }
  }, [token, logout]);

  const login = useCallback(async (email: string, password: string) => {
    const payload: LoginRequest = { email, password };
    setIsLoading(true);
    try {
      const response = await requestJson<TokenResponse>("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const stored: StoredToken = {
        accessToken: response.access_token,
        tokenType: response.token_type,
      };
      clearLogoutFlag();
      setStoredToken(stored);
      setToken(stored.accessToken);
      await refreshMe();
    } finally {
      setIsLoading(false);
    }
  }, [refreshMe]);

  const bootstrapCreateUser = useCallback(
    async (payload: AdminCreateUserRequest) => {
      const adminToken = import.meta.env.VITE_ADMIN_API_KEY;
      if (!adminToken) {
        throw new Error("Bootstrap disabled: missing VITE_ADMIN_API_KEY");
      }
      setIsLoading(true);
      try {
        const response = await requestJson<AdminCreateUserResponse>(
          "/auth/admin/users",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Admin-Token": adminToken,
            },
            body: JSON.stringify(payload),
          }
        );
        const stored: StoredToken = {
          accessToken: response.access_token,
          tokenType: response.token_type,
        };
        clearLogoutFlag();
        setStoredToken(stored);
        setToken(stored.accessToken);
        await refreshMe();
      } finally {
        setIsLoading(false);
      }
    },
    [refreshMe]
  );

  useEffect(() => {
    if (token) {
      void refreshMe().catch(() => undefined);
    }
  }, [token, refreshMe]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isLoading,
      login,
      logout,
      bootstrapCreateUser,
      refreshMe,
    }),
    [user, token, isLoading, login, logout, bootstrapCreateUser, refreshMe]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
