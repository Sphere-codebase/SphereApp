import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import Usage from "@/components/admin/organisms/Usage";
import WorkspaceTopBar from "@/components/workspace/WorkspaceTopBar";
import { useAuth } from "@/lib/auth/AuthContext";

export default function PlatformDashboardPage() {
  const navigate = useNavigate();
  const { me, logout } = useAuth();

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <WorkspaceTopBar
          title="Dashboard"
          subtitle={me?.clinic_name ?? "Platform"}
          isSending={false}
          showAdmin
          claimStatus={null}
          onLogout={handleUnauthorized}
        />
        <Usage />
      </div>
    </main>
  );
}
