import { Navigate } from "react-router-dom";

import { useAuth } from "@/lib/auth/AuthContext";

export default function AdminRoute({ children }: { children: JSX.Element }) {
  const { token, user, isLoading } = useAuth();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading || (token && !user)) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.roles.includes("admin")) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-sm text-slate-500">
        <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Access denied
        </div>
        <div>You need admin access to view this page.</div>
      </div>
    );
  }

  return children;
}
