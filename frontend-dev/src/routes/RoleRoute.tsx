import { Navigate } from "react-router-dom";

import { useAuth } from "@/lib/auth/AuthContext";
import type { UserRole } from "@/types/auth";

type RoleRouteProps = {
  allowedRoles: UserRole[];
  children: JSX.Element;
  redirectTo?: string;
};

export default function RoleRoute({
  allowedRoles,
  children,
  redirectTo = "/app/chat",
}: RoleRouteProps) {
  const { token, me, isAuthLoading, clinicBlocked, blockedMessage } = useAuth();

  if (clinicBlocked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-slate-800">
        <div className="max-w-md rounded-2xl border border-rose-200 bg-white p-6 text-center shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-500">
            Access blocked
          </div>
          <h1 className="mt-3 text-xl font-semibold">Clinic is blocked</h1>
          <p className="mt-2 text-sm text-slate-600">
            {blockedMessage ?? "Your clinic is blocked. Contact support for assistance."}
          </p>
        </div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (isAuthLoading || (token && !me)) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Loading...
      </div>
    );
  }

  if (!me) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(me.role)) {
    return <Navigate to={redirectTo} replace />;
  }

  return children;
}
