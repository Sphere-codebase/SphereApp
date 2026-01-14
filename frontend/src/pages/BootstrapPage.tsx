import { useState } from "react";
import { useNavigate } from "react-router-dom";

import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/AuthContext";
import type { AdminCreateUserRequest } from "@/lib/api/types";

export default function BootstrapPage() {
  const navigate = useNavigate();
  const { bootstrapCreateUser, isLoading } = useAuth();
  const adminToken = import.meta.env.VITE_ADMIN_API_KEY;
  const [error, setError] = useState<unknown>(null);
  const [form, setForm] = useState<AdminCreateUserRequest>({
    email: "",
    password: "",
    full_name: "",
    role: "admin",
    tenant_name: "",
  });

  const handleChange = (field: keyof AdminCreateUserRequest, value: string) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void (async () => {
      setError(null);
      try {
        await bootstrapCreateUser(form);
        navigate("/app/chat", { replace: true });
      } catch (err: unknown) {
        setError(err);
      }
    })();
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-10">
          <h1 className="text-3xl font-semibold">Bootstrap</h1>
          <p className="mt-3 text-sm text-slate-300">
            Placeholder for environment checks, dev-token auth, or seed flows.
          </p>
          {!adminToken ? (
            <p className="mt-6 text-sm text-slate-400">Bootstrap disabled.</p>
          ) : (
            <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit}>
              <label className="text-sm text-slate-300">
                Email
                <input
                  type="email"
                  className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100"
                  value={form.email}
                  onChange={(event) => handleChange("email", event.target.value)}
                  required
                />
              </label>
              <label className="text-sm text-slate-300">
                Password
                <input
                  type="password"
                  className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100"
                  value={form.password}
                  onChange={(event) => handleChange("password", event.target.value)}
                  required
                />
              </label>
              <label className="text-sm text-slate-300">
                Full name
                <input
                  type="text"
                  className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100"
                  value={form.full_name ?? ""}
                  onChange={(event) => handleChange("full_name", event.target.value)}
                />
              </label>
              <label className="text-sm text-slate-300">
                Role
                <input
                  type="text"
                  className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100"
                  value={form.role ?? ""}
                  onChange={(event) => handleChange("role", event.target.value)}
                />
              </label>
              <label className="text-sm text-slate-300">
                Tenant name
                <input
                  type="text"
                  className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100"
                  value={form.tenant_name ?? ""}
                  onChange={(event) => handleChange("tenant_name", event.target.value)}
                />
              </label>
              {error ? <ErrorNotice error={error} /> : null}
              <div>
                <Button type="submit" variant="secondary" disabled={isLoading}>
                  Run Bootstrap
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
