import { Navigate } from "react-router-dom";

import { useAuth } from "@/lib/auth/AuthContext";

export default function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { token, user, isLoading } = useAuth();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
