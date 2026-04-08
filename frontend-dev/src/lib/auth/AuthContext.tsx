import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

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

const AUTH_ME_QUERY_KEY = ["auth", "me"] as const;
const AUTH_ME_STALE_TIME = 2 * 60_000;
const AUTH_ME_GC_TIME = 10 * 60_000;

export interface AuthContextValue {
  me: MeDTO | null;
  token: string | null;
  isAuthLoading: boolean;
  clinicBlocked: boolean;
  blockedMessage: string | null;
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
  const queryClient = useQueryClient();
  const [me, setMe] = useState<MeDTO | null>(null);
  const [token, setToken] = useState<string | null>(getInitialToken);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [clinicBlocked, setClinicBlocked] = useState(false);
  const [blockedMessage, setBlockedMessage] = useState<string | null>(null);

  const clearCachedMe = useCallback(() => {
    queryClient.removeQueries({ queryKey: AUTH_ME_QUERY_KEY });
  }, [queryClient]);

  const logout = useCallback(() => {
    setLogoutFlag();
    setToken(null);
    setMe(null);
    clearCachedMe();
  }, [clearCachedMe]);

  const handleClinicBlocked = useCallback(() => {
    setClinicBlocked(true);
    setBlockedMessage("Your clinic is blocked. Contact support for assistance.");
    setLogoutFlag();
    setToken(null);
    setMe(null);
    clearCachedMe();
  }, [clearCachedMe]);

  const refreshMe = useCallback(async () => {
    const storedToken = isLogoutFlagSet() ? null : getStoredToken()?.accessToken ?? null;
    const currentToken = token ?? storedToken ?? null;
    if (!currentToken) {
      setMe(null);
      setIsAuthLoading(false);
      clearCachedMe();
      return;
    }

    const cachedMe = queryClient.getQueryData<MeDTO>(AUTH_ME_QUERY_KEY);
    const queryState = queryClient.getQueryState<MeDTO>(AUTH_ME_QUERY_KEY);
    const isFresh =
      queryState?.dataUpdatedAt != null &&
      Date.now() - queryState.dataUpdatedAt < AUTH_ME_STALE_TIME;

    if (cachedMe) {
      setMe(cachedMe);
      setIsAuthLoading(false);
      if (isFresh) {
        return;
      }
      void queryClient
        .fetchQuery({
          queryKey: AUTH_ME_QUERY_KEY,
          queryFn: getMe,
          staleTime: AUTH_ME_STALE_TIME,
          gcTime: AUTH_ME_GC_TIME,
        })
        .then((meResponse) => {
          if (!meResponse.is_active) {
            logout();
            return;
          }
          setClinicBlocked(false);
          setBlockedMessage(null);
          setMe(meResponse);
        })
        .catch((error) => {
          if (error instanceof ApiError) {
            if (error.payload?.error.code === "CLINIC_BLOCKED") {
              handleClinicBlocked();
              return;
            }
            if (error.status === 401 || error.status === 403) {
              logout();
              return;
            }
          }
        });
      return;
    }

    setIsAuthLoading(true);
    try {
      const meResponse = await queryClient.fetchQuery({
        queryKey: AUTH_ME_QUERY_KEY,
        queryFn: getMe,
        staleTime: AUTH_ME_STALE_TIME,
        gcTime: AUTH_ME_GC_TIME,
      });
      if (!meResponse.is_active) {
        logout();
        return;
      }
      setClinicBlocked(false);
      setBlockedMessage(null);
      setMe(meResponse);
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.payload?.error.code === "CLINIC_BLOCKED") {
          handleClinicBlocked();
          return;
        }
        if (error.status === 401 || error.status === 403) {
          logout();
          return;
        }
      }
      throw error;
    } finally {
      setIsAuthLoading(false);
    }
  }, [token, queryClient, clearCachedMe, logout, handleClinicBlocked]);

  const login = useCallback(async (email: string, password: string) => {
    setIsAuthLoading(true);
    setClinicBlocked(false);
    setBlockedMessage(null);
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
        setClinicBlocked(false);
        setBlockedMessage(null);
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
      clinicBlocked,
      blockedMessage,
      login,
      logout,
      hasRole,
      bootstrapCreateUser,
      refreshMe,
    }),
    [
      me,
      token,
      isAuthLoading,
      clinicBlocked,
      blockedMessage,
      login,
      logout,
      hasRole,
      bootstrapCreateUser,
      refreshMe,
    ]
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
