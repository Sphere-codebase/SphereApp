import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, me, isAuthLoading, clinicBlocked, blockedMessage } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (me) {
      const returnTo = searchParams.get("returnTo");
      const normalized = returnTo?.startsWith("/app/") ? returnTo : null;
      const role = me.role;
      const allow = (roles: string[]) => roles.includes(role);
      const isAllowedReturnTo = (path: string) => {
        if (path.startsWith("/app/platform")) {
          return role === "platform_staff_admin";
        }
        if (path.startsWith("/app/clinic")) {
          return allow(["chief_doctor", "clinic_admin"]);
        }
        if (path.startsWith("/app/admin")) {
          return allow(["platform_staff_admin", "clinic_admin", "chief_doctor"]);
        }
        if (
          path.startsWith("/app/chat") ||
          path.startsWith("/app/workspace") ||
          path.startsWith("/app/patients") ||
          path.startsWith("/app/ai-history") ||
          path.startsWith("/app/insurance-rules")
        ) {
          return allow(["doctor", "chief_doctor", "clinic_admin", "platform_staff_admin"]);
        }
        if (path.startsWith("/app/dashboard")) {
          return allow([
            "doctor",
            "chief_doctor",
            "clinic_admin",
            "platform_staff_admin",
          ]);
        }
        return false;
      };
      const nextRoute =
        normalized && isAllowedReturnTo(normalized) ? normalized : "/app/chat";
      navigate(nextRoute, { replace: true });
    }
  }, [me, navigate, searchParams]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void (async () => {
      setError(null);
      try {
        await login(email, password);
      } catch (err: unknown) {
        setError(err);
      }
    })();
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-100 via-white to-slate-200">
      <div className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6">
        <div className="rounded-3xl border border-slate-200 bg-white/70 p-10 shadow-lg backdrop-blur">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            SphereApp API
          </p>
          <h1 className="mt-3 text-3xl font-semibold text-slate-900">Login</h1>
          <p className="mt-2 max-w-xl text-sm text-slate-600">
            Placeholder login screen. Wire up JWT auth once the API client is connected.
          </p>
          {clinicBlocked ? (
            <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {blockedMessage ?? "Your clinic is blocked. Contact support for assistance."}
            </div>
          ) : null}
          <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit}>
            <label className="text-sm font-medium text-slate-700">
              Email
              <input
                type="email"
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
                placeholder="doctor@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Password
              <input
                type="password"
                className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm"
                placeholder="••••••••"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            {error ? <ErrorNotice error={error} /> : null}
            <div className="flex gap-3">
              <Button type="submit" disabled={isAuthLoading}>
                Sign in
              </Button>
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}
