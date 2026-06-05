import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import {
  createPlatformClinic,
  listPlatformClinics,
  updatePlatformClinic,
} from "@/api/platformAdmin";
import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import type { PlatformClinicDTO } from "@/types/platformAdmin";
import Usage from "./Usage";

const PAGE_LIMIT = 25;
const CACHE_TTL_MS = 5 * 60 * 1000;

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function Clinics() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<PlatformClinicDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [billingModalOpen, setBillingModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [editingClinic, setEditingClinic] = useState<PlatformClinicDTO | null>(null);

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [billingProviderNpi, setBillingProviderNpi] = useState("");
  const [billingProviderTaxId, setBillingProviderTaxId] = useState("");
  const [billingProviderOrganizationName, setBillingProviderOrganizationName] =
    useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zip, setZip] = useState("");
  const [country, setCountry] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<string>("clinics");

  const cacheRef = useRef<
    Map<
      string,
      { timestamp: number; data: { items: PlatformClinicDTO[]; total: number } }
    >
  >(new Map());

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const cacheKey = `${query}:${offset}`;

  const loadClinics = useCallback(async () => {
    const cached = cacheRef.current.get(cacheKey);
    const now = Date.now();
    if (cached && now - cached.timestamp < CACHE_TTL_MS) {
      setItems(cached.data.items);
      setTotal(cached.data.total);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await listPlatformClinics({
        query: query || undefined,
        limit: PAGE_LIMIT,
        offset,
      });
      setItems(response.items);
      setTotal(response.total);
      cacheRef.current.set(cacheKey, {
        timestamp: now,
        data: { items: response.items, total: response.total },
      });
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to load clinics.");
    } finally {
      setIsLoading(false);
    }
  }, [cacheKey, query, offset, handleUnauthorized]);

  useEffect(() => {
    void loadClinics();
  }, [loadClinics]);

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    setOffset(0);
    cacheRef.current.clear();
    void loadClinics();
  };

  const handleCreateClinic = async () => {
    if (!name.trim()) {
      setFormError("Clinic name is required.");
      return;
    }
    setCreating(true);
    setFormError(null);
    try {
      await createPlatformClinic({
        name: name.trim(),
        phone: phone.trim() || null,
        billing_provider_npi: billingProviderNpi.trim() || null,
        billing_provider_tax_id: billingProviderTaxId.trim() || null,
        billing_provider_organization_name:
          billingProviderOrganizationName.trim() || null,
        address:
          line1 || city || state || zip || country || line2
            ? {
                line1: line1.trim() || null,
                line2: line2.trim() || null,
                city: city.trim() || null,
                state: state.trim() || null,
                zip: zip.trim() || null,
                country: country.trim() || null,
              }
            : null,
      });
      setModalOpen(false);
      setName("");
      setPhone("");
      setBillingProviderNpi("");
      setBillingProviderTaxId("");
      setBillingProviderOrganizationName("");
      setLine1("");
      setLine2("");
      setCity("");
      setState("");
      setZip("");
      setCountry("");
      cacheRef.current.clear();
      void loadClinics();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setFormError("Unable to create clinic.");
    } finally {
      setCreating(false);
    }
  };

  const openBillingDialog = (clinic: PlatformClinicDTO) => {
    setEditingClinic(clinic);
    setBillingProviderNpi(clinic.billing_provider_npi ?? "");
    setBillingProviderTaxId(clinic.billing_provider_tax_id ?? "");
    setBillingProviderOrganizationName(
      clinic.billing_provider_organization_name ?? ""
    );
    setFormError(null);
    setBillingModalOpen(true);
  };

  const handleBillingProfileSave = async () => {
    if (!editingClinic?.id) return;
    setSavingId(editingClinic.id);
    setFormError(null);
    try {
      const updated = await updatePlatformClinic(editingClinic.id, {
        billing_provider_npi: billingProviderNpi.trim() || null,
        billing_provider_tax_id: billingProviderTaxId.trim() || null,
        billing_provider_organization_name:
          billingProviderOrganizationName.trim() || null,
      });
      setItems((prev) =>
        prev.map((item) => (item.id === editingClinic.id ? updated : item))
      );
      cacheRef.current.clear();
      setBillingModalOpen(false);
      setEditingClinic(null);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setFormError("Unable to update billing provider profile.");
    } finally {
      setSavingId(null);
    }
  };

  const handleToggleBlock = async (clinic: PlatformClinicDTO) => {
    if (!clinic.id) return;
    const nextBlocked = !clinic.is_blocked;
    const confirmed = window.confirm(
      nextBlocked ? "Block this clinic? Users will lose access." : "Unblock this clinic?"
    );
    if (!confirmed) return;
    setSavingId(clinic.id);
    setError(null);
    try {
      const updated = await updatePlatformClinic(clinic.id, { is_blocked: nextBlocked });
      setItems((prev) => prev.map((item) => (item.id === clinic.id ? updated : item)));
      cacheRef.current.clear();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        handleUnauthorized();
        return;
      }
      setError("Unable to update clinic status.");
    } finally {
      setSavingId(null);
    }
  };

  const totalPages = useMemo(() => Math.ceil(total / PAGE_LIMIT), [total]);
  const currentPage = useMemo(() => Math.floor(offset / PAGE_LIMIT) + 1, [offset]);

  return (
    <>
      <section className="flex min-h-screen flex-col gap-6">
        <div className="flex flex-wrap items-center gap-2">
          {activeTab === "clinics" ? (
            <>
              <Button type="button" onClick={() => setModalOpen(true)}>
                Create Clinic
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setActiveTab("usage")}
              >
                Usage Overview
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={() => setActiveTab("clinics")}
              >
                Clinics
              </Button>
              <Button type="button" variant="default">
                Usage Overview
              </Button>
            </>
          )}
        </div>

        {activeTab === "clinics" ? (
          <>
            <form
              onSubmit={handleSearch}
              className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"
            >
              <input
                type="text"
                placeholder="Search clinics by name"
                className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <Button type="submit" variant="secondary">
                Search
              </Button>
            </form>

            {error ? <ErrorNotice error={error} /> : null}

            <Card className="rounded-3xl border-slate-200 shadow-sm dark:border-slate-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Clinic List</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <div
                        key={`clinic-skeleton-${index}`}
                        className="h-14 rounded-2xl bg-slate-100 dark:bg-slate-800"
                      />
                    ))}
                  </div>
                ) : items.length === 0 ? (
                  <div className="text-sm text-slate-500">No clinics found.</div>
                ) : (
                  items.map((clinic) => (
                    <div
                      key={clinic.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                    >
                      <div className="flex flex-1 flex-col gap-1">
                        <div className="text-sm font-semibold text-slate-900 dark:text-white">
                          {clinic.name}
                        </div>
                        <div className="text-xs text-slate-500">
                          Created: {formatDate(clinic.created_at)} · Phone:{" "}
                          {clinic.phone ?? "—"}
                        </div>
                        <div className="text-xs text-slate-500">
                          Doctors: {clinic.counters?.doctors_count ?? 0} · Patients:{" "}
                          {clinic.counters?.patients_count ?? 0} · Claims (30d):{" "}
                          {clinic.counters?.claims_30d ?? 0}
                        </div>
                        <div className="text-xs text-slate-500">
                          Billing provider:{" "}
                          {clinic.billing_provider_organization_name ?? "—"} · NPI:{" "}
                          {clinic.billing_provider_npi ?? "—"} · Tax ID:{" "}
                          {clinic.billing_provider_tax_id ?? "—"}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold ${
                            clinic.is_blocked
                              ? "bg-rose-100 text-rose-700"
                              : "bg-emerald-100 text-emerald-700"
                          }`}
                        >
                          {clinic.is_blocked ? "Blocked" : "Active"}
                        </span>
                        <Button
                          type="button"
                          size="sm"
                          variant={clinic.is_blocked ? "secondary" : "outline"}
                          onClick={() => void handleToggleBlock(clinic)}
                          disabled={savingId === clinic.id}
                        >
                          {savingId === clinic.id
                            ? "Saving..."
                            : clinic.is_blocked
                              ? "Unblock"
                              : "Block"}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => openBillingDialog(clinic)}
                          disabled={savingId === clinic.id}
                        >
                          Billing
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
              <div>
                Showing {items.length} of {total} clinics
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_LIMIT))}
                  disabled={offset === 0 || isLoading}
                >
                  Previous
                </Button>
                <span>
                  Page {currentPage} of {totalPages || 1}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setOffset((prev) => prev + PAGE_LIMIT)}
                  disabled={offset + PAGE_LIMIT >= total || isLoading}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        ) : (
          <Usage />
        )}
      </section>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-lg dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
          <DialogHeader>
            <DialogTitle>Create Clinic</DialogTitle>
            <DialogDescription className="dark:text-slate-300">
              Add a new clinic to the platform.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Clinic name *
              <input
                type="text"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Phone
              <input
                type="text"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Billing provider organization
              <input
                type="text"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={billingProviderOrganizationName}
                onChange={(event) =>
                  setBillingProviderOrganizationName(event.target.value)
                }
              />
            </label>
            <div className="grid gap-2 md:grid-cols-2">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Billing provider NPI
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={billingProviderNpi}
                  onChange={(event) => setBillingProviderNpi(event.target.value)}
                />
              </label>
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Billing provider tax ID
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={billingProviderTaxId}
                  onChange={(event) => setBillingProviderTaxId(event.target.value)}
                />
              </label>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Address line 1
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={line1}
                  onChange={(event) => setLine1(event.target.value)}
                />
              </label>
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Address line 2
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={line2}
                  onChange={(event) => setLine2(event.target.value)}
                />
              </label>
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                City
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={city}
                  onChange={(event) => setCity(event.target.value)}
                />
              </label>
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                State
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={state}
                  onChange={(event) => setState(event.target.value)}
                />
              </label>
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Zip
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={zip}
                  onChange={(event) => setZip(event.target.value)}
                />
              </label>
              <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Country
                <input
                  type="text"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  value={country}
                  onChange={(event) => setCountry(event.target.value)}
                />
              </label>
            </div>
            {formError ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
                {formError}
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button type="button" onClick={handleCreateClinic} disabled={creating}>
              {creating ? "Creating..." : "Create Clinic"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={billingModalOpen} onOpenChange={setBillingModalOpen}>
        <DialogContent className="max-w-lg dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
          <DialogHeader>
            <DialogTitle>Billing Provider</DialogTitle>
            <DialogDescription className="dark:text-slate-300">
              Maintain the clinic billing profile used for payer status checks.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Organization name
              <input
                type="text"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={billingProviderOrganizationName}
                onChange={(event) =>
                  setBillingProviderOrganizationName(event.target.value)
                }
              />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              NPI
              <input
                type="text"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={billingProviderNpi}
                onChange={(event) => setBillingProviderNpi(event.target.value)}
              />
            </label>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Tax ID
              <input
                type="text"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                value={billingProviderTaxId}
                onChange={(event) => setBillingProviderTaxId(event.target.value)}
              />
            </label>
            {formError ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
                {formError}
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setBillingModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleBillingProfileSave}
              disabled={savingId === editingClinic?.id}
            >
              {savingId === editingClinic?.id ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
