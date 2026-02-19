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
  redirectTo = "/app/dashboard",
}: RoleRouteProps) {
  const { token, me, isAuthLoading } = useAuth();

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
