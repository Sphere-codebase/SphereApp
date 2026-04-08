import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listClinicDoctors, updateClinicDoctor } from "@/api/clinicAdmin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import type { DoctorUserDTO } from "@/types/clinicAdmin";

const ROLE_OPTIONS: DoctorUserDTO["role"][] = [
  "doctor",
  "chief_doctor",
  "clinic_admin",
];

function formatRoleLabel(role: string): string {
  return role
    .replace("_", " ")
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function ClinicDoctorsPage() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const [doctors, setDoctors] = useState<DoctorUserDTO[]>([]);
  const [pendingEdits, setPendingEdits] = useState<
    Record<number, Partial<Pick<DoctorUserDTO, "role" | "is_active">>>
  >({});
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const loadDoctors = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listClinicDoctors();
      setDoctors(response.items);
      setPendingEdits({});
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load doctors.");
    } finally {
      setIsLoading(false);
    }
  }, [handleUnauthorized]);

  useEffect(() => {
    void loadDoctors();
  }, [loadDoctors]);

  const handleEdit = (id: number, changes: Partial<Pick<DoctorUserDTO, "role" | "is_active">>) => {
    setPendingEdits((prev) => ({
      ...prev,
      [id]: { ...prev[id], ...changes },
    }));
  };

  const handleSave = async (doctor: DoctorUserDTO) => {
    const changes = pendingEdits[doctor.id];
    if (!changes || Object.keys(changes).length === 0) {
      return;
    }
    if (changes.role && (changes.role === "clinic_admin" || doctor.role === "clinic_admin")) {
      const confirmed = window.confirm(
        "Changing clinic admin roles affects permissions. Continue?"
      );
      if (!confirmed) {
        return;
      }
    }
    setSavingIds((prev) => new Set(prev).add(doctor.id));
    setError(null);
    try {
      const updated = await updateClinicDoctor(doctor.id, changes);
      setDoctors((prev) => prev.map((item) => (item.id === doctor.id ? updated : item)));
      setPendingEdits((prev) => {
        const next = { ...prev };
        delete next[doctor.id];
        return next;
      });
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to save doctor changes.");
    } finally {
      setSavingIds((prev) => {
        const next = new Set(prev);
        next.delete(doctor.id);
        return next;
      });
    }
  };

  const rows = useMemo(() => doctors, [doctors]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              {me?.clinic_name ?? "Clinic"}
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Doctors
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/app/clinic")}
            >
              Clinic Dashboard
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/app/clinic/audit")}
            >
              Audit Logs
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {error}
          </div>
        ) : null}

        <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Clinic Doctors</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={`doctor-skeleton-${index}`} className="h-14 rounded-2xl bg-slate-100 dark:bg-slate-800" />
                ))}
              </div>
            ) : rows.length === 0 ? (
              <div className="text-sm text-slate-500">No doctors found.</div>
            ) : (
              <div className="space-y-3">
                {rows.map((doctor) => {
                  const pending = pendingEdits[doctor.id] ?? {};
                  const nextRole = pending.role ?? doctor.role;
                  const nextActive = pending.is_active ?? doctor.is_active;
                  const hasChanges = Object.keys(pending).length > 0;
                  return (
                    <div
                      key={doctor.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                    >
                      <div className="flex flex-1 flex-col gap-1">
                        <div className="text-sm font-semibold text-slate-900 dark:text-white">
                          {doctor.full_name ?? "Unnamed"}
                        </div>
                        <div className="text-xs text-slate-500">{doctor.email}</div>
                      </div>
                      <div className="flex flex-wrap items-center gap-3">
                        <select
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                          value={nextRole}
                          onChange={(event) => handleEdit(doctor.id, { role: event.target.value as DoctorUserDTO["role"] })}
                        >
                          {ROLE_OPTIONS.map((role) => (
                            <option key={role} value={role}>
                              {formatRoleLabel(role)}
                            </option>
                          ))}
                        </select>
                        <label className="flex items-center gap-2 text-xs text-slate-500">
                          <input
                            type="checkbox"
                            checked={nextActive}
                            onChange={(event) => handleEdit(doctor.id, { is_active: event.target.checked })}
                          />
                          Active
                        </label>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => void handleSave(doctor)}
                          disabled={!hasChanges || savingIds.has(doctor.id)}
                        >
                          {savingIds.has(doctor.id) ? "Saving..." : "Save"}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
