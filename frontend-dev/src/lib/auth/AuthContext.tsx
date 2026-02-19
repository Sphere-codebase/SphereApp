import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { login as loginApi, getMe } from "@/api/auth";
import { requestJson } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AdminCreateUserRequest, AdminCreateUserResponse } from "@/lib/api/types";
import {
  clearLogoutFlag,
  getStoredToken,
  isLogoutFlagSet,
  setLogoutFlag,
  setStoredToken,
  type StoredToken,
} from "@/lib/auth/token";
import type { MeDTO, UserRole } from "@/types/auth";

export interface AuthContextValue {
  me: MeDTO | null;
  token: string | null;
  isAuthLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
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
  const [me, setMe] = useState<MeDTO | null>(null);
  const [token, setToken] = useState<string | null>(getInitialToken);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  const logout = useCallback(() => {
    setLogoutFlag();
    setToken(null);
    setMe(null);
  }, []);

  const refreshMe = useCallback(async () => {
    const storedToken = isLogoutFlagSet() ? null : getStoredToken()?.accessToken ?? null;
    const currentToken = token ?? storedToken ?? null;
    if (!currentToken) {
      setMe(null);
      setIsAuthLoading(false);
      return;
    }
    setIsAuthLoading(true);
    try {
      const meResponse = await getMe();
      if (!meResponse.is_active) {
        logout();
        return;
      }
      setMe(meResponse);
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        logout();
      } else {
        throw error;
      }
    } finally {
      setIsAuthLoading(false);
    }
  }, [token, logout]);

  const login = useCallback(async (email: string, password: string) => {
    setIsAuthLoading(true);
    try {
      const response = await loginApi(email, password);
      const stored: StoredToken = {
        accessToken: response.access_token,
        tokenType: response.token_type ?? "bearer",
      };
      clearLogoutFlag();
      setStoredToken(stored);
      setToken(stored.accessToken);
      await refreshMe();
    } finally {
      setIsAuthLoading(false);
    }
  }, [refreshMe]);

  const bootstrapCreateUser = useCallback(
    async (payload: AdminCreateUserRequest) => {
      const adminToken = import.meta.env.VITE_ADMIN_API_KEY;
      if (!adminToken) {
        throw new Error("Bootstrap disabled: missing VITE_ADMIN_API_KEY");
      }
      setIsAuthLoading(true);
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
        setIsAuthLoading(false);
      }
    },
    [refreshMe]
  );

  useEffect(() => {
    void refreshMe().catch(() => undefined);
  }, [token, refreshMe]);

  const hasRole = useCallback(
    (roles: UserRole | UserRole[]) => {
      if (!me) {
        return false;
      }
      const allowed = Array.isArray(roles) ? roles : [roles];
      return allowed.includes(me.role);
    },
    [me]
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      me,
      token,
      isAuthLoading,
      login,
      logout,
      hasRole,
      bootstrapCreateUser,
      refreshMe,
    }),
    [me, token, isAuthLoading, login, logout, hasRole, bootstrapCreateUser, refreshMe]
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
