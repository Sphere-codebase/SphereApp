import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth/AuthContext";
import {
  createAgency,
  createPolicyLink,
  deleteAgency,
  deletePolicyLink,
  listAgencies,
  listPolicyLinks,
  listProcedureCodes,
  updateAgency,
  updatePolicyLink,
  type Agency,
  type AgencyCreateInput,
  type PolicyLink,
  type PolicyLinkCreateInput,
  type ProcedureCode,
} from "@/lib/api/admin";
import { ApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import { Pencil, Plus, Trash2 } from "lucide-react";

type TabKey = "agencies" | "policy-links";

interface AgencyFormState {
  name: string;
  slug: string;
  is_active: boolean;
}

interface PolicyFormState {
  agency_id: string;
  procedure_code_id: string;
  policy_url: string;
  effective_from: string;
  effective_to: string;
  status: "ACTIVE" | "INACTIVE";
  notes: string;
}

const emptyAgencyForm: AgencyFormState = {
  name: "",
  slug: "",
  is_active: true,
};

const emptyPolicyForm: PolicyFormState = {
  agency_id: "",
  procedure_code_id: "",
  policy_url: "",
  effective_from: "",
  effective_to: "",
  status: "ACTIVE",
  notes: "",
};

function formatDateInput(value?: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toISOString().slice(0, 10);
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString();
}

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabKey>("agencies");
  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [procedureCodes, setProcedureCodes] = useState<ProcedureCode[]>([]);
  const [policyLinks, setPolicyLinks] = useState<PolicyLink[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [agencyDialogOpen, setAgencyDialogOpen] = useState(false);
  const [policyDialogOpen, setPolicyDialogOpen] = useState(false);
  const [editingAgency, setEditingAgency] = useState<Agency | null>(null);
  const [editingPolicy, setEditingPolicy] = useState<PolicyLink | null>(null);
  const [agencyForm, setAgencyForm] = useState<AgencyFormState>(emptyAgencyForm);
  const [policyForm, setPolicyForm] = useState<PolicyFormState>(emptyPolicyForm);
  const [filters, setFilters] = useState({
    agency_id: "",
    procedure_code_id: "",
    query: "",
  });

  const agencyById = useMemo(() => {
    return new Map(agencies.map((agency) => [agency.id, agency]));
  }, [agencies]);

  const codeById = useMemo(() => {
    return new Map(procedureCodes.map((code) => [code.id, code]));
  }, [procedureCodes]);

  const handleApiError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        navigate("/login");
        return;
      }
      setError(err);
    },
    [logout, navigate]
  );

  const loadAgencies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listAgencies();
      setAgencies(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError]);

  const loadProcedureCodes = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listProcedureCodes();
      setProcedureCodes(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError]);

  const loadPolicyLinks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const filterPayload: {
        agency_id?: string;
        procedure_code_id?: string;
        query?: string;
      } = {};
      if (filters.agency_id) {
        filterPayload.agency_id = filters.agency_id;
      }
      if (filters.procedure_code_id) {
        filterPayload.procedure_code_id = filters.procedure_code_id;
      }
      if (filters.query) {
        filterPayload.query = filters.query;
      }
      const data = await listPolicyLinks(filterPayload);
      setPolicyLinks(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [filters, handleApiError]);

  useEffect(() => {
    if (user?.is_admin) {
      void loadAgencies();
    }
  }, [loadAgencies, user]);

  useEffect(() => {
    if (user?.is_admin && activeTab === "policy-links") {
      void loadProcedureCodes();
      void loadPolicyLinks();
    }
  }, [activeTab, loadPolicyLinks, loadProcedureCodes, user]);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!user.is_admin) {
    return <Navigate to="/app/chat" replace />;
  }

  const openAgencyDialog = (agency: Agency | null) => {
    setEditingAgency(agency);
    setAgencyForm(
      agency
        ? {
            name: agency.name,
            slug: agency.slug,
            is_active: agency.is_active,
          }
        : emptyAgencyForm
    );
    setAgencyDialogOpen(true);
  };

  const openPolicyDialog = (policy: PolicyLink | null) => {
    setEditingPolicy(policy);
    setPolicyForm(
      policy
        ? {
            agency_id: policy.agency_id,
            procedure_code_id: policy.procedure_code_id,
            policy_url: policy.policy_url,
            effective_from: formatDateInput(policy.effective_from),
            effective_to: formatDateInput(policy.effective_to),
            status: policy.status,
            notes: policy.notes ?? "",
          }
        : emptyPolicyForm
    );
    setPolicyDialogOpen(true);
  };

  const handleAgencySubmit = async () => {
    setError(null);
    const payload: AgencyCreateInput = {
      name: agencyForm.name.trim(),
      slug: agencyForm.slug.trim(),
      is_active: agencyForm.is_active,
    };
    if (!payload.name || !payload.slug) {
      return;
    }
    try {
      if (editingAgency) {
        await updateAgency(editingAgency.id, payload);
      } else {
        await createAgency(payload);
      }
      setAgencyDialogOpen(false);
      await loadAgencies();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleAgencyDelete = async (agencyId: string) => {
    setError(null);
    try {
      await deleteAgency(agencyId);
      setAgencies((prev) => prev.filter((agency) => agency.id !== agencyId));
    } catch (err) {
      handleApiError(err);
    }
  };

  const handlePolicySubmit = async () => {
    setError(null);
    const payload: PolicyLinkCreateInput = {
      agency_id: policyForm.agency_id,
      procedure_code_id: policyForm.procedure_code_id,
      policy_url: policyForm.policy_url.trim(),
      effective_from: policyForm.effective_from ? policyForm.effective_from : null,
      effective_to: policyForm.effective_to ? policyForm.effective_to : null,
      status: policyForm.status,
      notes: policyForm.notes ? policyForm.notes.trim() : null,
    };
    if (!payload.agency_id || !payload.procedure_code_id || !payload.policy_url) {
      return;
    }
    try {
      if (editingPolicy) {
        await updatePolicyLink(editingPolicy.id, payload);
      } else {
        await createPolicyLink(payload);
      }
      setPolicyDialogOpen(false);
      await loadPolicyLinks();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handlePolicyDelete = async (policyId: string) => {
    setError(null);
    try {
      await deletePolicyLink(policyId);
      setPolicyLinks((prev) => prev.filter((link) => link.id !== policyId));
    } catch (err) {
      handleApiError(err);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Admin
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Catalogs
            </h1>
          </div>
          <Button type="button" variant="outline" onClick={() => navigate("/app/chat")}>
            Back to chat
          </Button>
        </header>

        <div className="flex flex-wrap gap-2">
          {(["agencies", "policy-links"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              className={cn(
                "rounded-full px-4 py-2 text-sm font-medium",
                activeTab === tab
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "bg-white text-slate-600 shadow-sm dark:bg-slate-900 dark:text-slate-300"
              )}
              onClick={() => setActiveTab(tab)}
            >
              {tab === "agencies" ? "Agencies" : "Policy Links"}
            </button>
          ))}
        </div>

        {error ? <ErrorNotice error={error} /> : null}

        {activeTab === "agencies" ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Agencies</h2>
              <Dialog open={agencyDialogOpen} onOpenChange={setAgencyDialogOpen}>
                <DialogTrigger asChild>
                  <Button type="button" onClick={() => openAgencyDialog(null)}>
                    <Plus className="h-4 w-4" />
                    New agency
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{editingAgency ? "Edit agency" : "New agency"}</DialogTitle>
                    <DialogDescription>Manage agency details.</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-3">
                    <label className="flex flex-col gap-1 text-sm">
                      Name
                      <input
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        value={agencyForm.name}
                        onChange={(event) =>
                          setAgencyForm((prev) => ({ ...prev, name: event.target.value }))
                        }
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                      Slug
                      <input
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        value={agencyForm.slug}
                        onChange={(event) =>
                          setAgencyForm((prev) => ({ ...prev, slug: event.target.value }))
                        }
                      />
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={agencyForm.is_active}
                        onChange={(event) =>
                          setAgencyForm((prev) => ({
                            ...prev,
                            is_active: event.target.checked,
                          }))
                        }
                      />
                      Active
                    </label>
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="secondary" onClick={() => setAgencyDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button type="button" onClick={() => void handleAgencySubmit()}>
                      Save
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2">Name</th>
                    <th className="py-2">Slug</th>
                    <th className="py-2">Active</th>
                    <th className="py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {agencies.map((agency) => (
                    <tr key={agency.id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-3 font-medium">{agency.name}</td>
                      <td className="py-3 text-slate-500">{agency.slug}</td>
                      <td className="py-3">{agency.is_active ? "Yes" : "No"}</td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => openAgencyDialog(agency)}
                            aria-label={`Edit ${agency.name}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void handleAgencyDelete(agency.id)}
                            aria-label={`Delete ${agency.name}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!isLoading && agencies.length === 0 ? (
                    <tr>
                      <td className="py-6 text-center text-sm text-slate-500" colSpan={4}>
                        No agencies yet.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Policy links</h2>
              <Dialog open={policyDialogOpen} onOpenChange={setPolicyDialogOpen}>
                <DialogTrigger asChild>
                  <Button type="button" onClick={() => openPolicyDialog(null)}>
                    <Plus className="h-4 w-4" />
                    New link
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{editingPolicy ? "Edit policy link" : "New policy link"}</DialogTitle>
                    <DialogDescription>Attach policy links to CPT codes.</DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-3">
                    <label className="flex flex-col gap-1 text-sm">
                      Agency
                      <select
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        value={policyForm.agency_id}
                        onChange={(event) =>
                          setPolicyForm((prev) => ({ ...prev, agency_id: event.target.value }))
                        }
                      >
                        <option value="">Select agency</option>
                        {agencies.map((agency) => (
                          <option key={agency.id} value={agency.id}>
                            {agency.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                      Procedure code
                      <select
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        value={policyForm.procedure_code_id}
                        onChange={(event) =>
                          setPolicyForm((prev) => ({
                            ...prev,
                            procedure_code_id: event.target.value,
                          }))
                        }
                      >
                        <option value="">Select code</option>
                        {procedureCodes.map((code) => (
                          <option key={code.id} value={code.id}>
                            {code.code} {code.title ? `— ${code.title}` : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                      Policy URL
                      <input
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        value={policyForm.policy_url}
                        onChange={(event) =>
                          setPolicyForm((prev) => ({ ...prev, policy_url: event.target.value }))
                        }
                      />
                    </label>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="flex flex-col gap-1 text-sm">
                        Effective from
                        <input
                          type="date"
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                          value={policyForm.effective_from}
                          onChange={(event) =>
                            setPolicyForm((prev) => ({
                              ...prev,
                              effective_from: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label className="flex flex-col gap-1 text-sm">
                        Effective to
                        <input
                          type="date"
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                          value={policyForm.effective_to}
                          onChange={(event) =>
                            setPolicyForm((prev) => ({
                              ...prev,
                              effective_to: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </div>
                    <label className="flex flex-col gap-1 text-sm">
                      Status
                      <select
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        value={policyForm.status}
                        onChange={(event) =>
                          setPolicyForm((prev) => ({
                            ...prev,
                            status: event.target.value === "ACTIVE" ? "ACTIVE" : "INACTIVE",
                          }))
                        }
                      >
                        <option value="ACTIVE">ACTIVE</option>
                        <option value="INACTIVE">INACTIVE</option>
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                      Notes
                      <textarea
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        value={policyForm.notes}
                        onChange={(event) =>
                          setPolicyForm((prev) => ({ ...prev, notes: event.target.value }))
                        }
                      />
                    </label>
                  </div>
                  <DialogFooter>
                    <Button type="button" variant="secondary" onClick={() => setPolicyDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button type="button" onClick={() => void handlePolicySubmit()}>
                      Save
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            <div className="mt-4 grid gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-950">
              <div className="grid gap-3 md:grid-cols-4">
                <label className="flex flex-col gap-1">
                  Agency
                  <select
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                    value={filters.agency_id}
                    onChange={(event) =>
                      setFilters((prev) => ({ ...prev, agency_id: event.target.value }))
                    }
                  >
                    <option value="">All</option>
                    {agencies.map((agency) => (
                      <option key={agency.id} value={agency.id}>
                        {agency.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  Procedure code
                  <select
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                    value={filters.procedure_code_id}
                    onChange={(event) =>
                      setFilters((prev) => ({
                        ...prev,
                        procedure_code_id: event.target.value,
                      }))
                    }
                  >
                    <option value="">All</option>
                    {procedureCodes.map((code) => (
                      <option key={code.id} value={code.id}>
                        {code.code}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 md:col-span-2">
                  Search
                  <input
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                    value={filters.query}
                    onChange={(event) =>
                      setFilters((prev) => ({ ...prev, query: event.target.value }))
                    }
                  />
                </label>
              </div>
              <div className="flex justify-end">
                <Button type="button" variant="outline" onClick={() => void loadPolicyLinks()}>
                  Apply filters
                </Button>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2">Agency</th>
                    <th className="py-2">Procedure</th>
                    <th className="py-2">Policy URL</th>
                    <th className="py-2">Status</th>
                    <th className="py-2">Updated</th>
                    <th className="py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {policyLinks.map((link) => {
                    const agency = agencyById.get(link.agency_id);
                    const code = codeById.get(link.procedure_code_id);
                    return (
                      <tr
                        key={link.id}
                        className="border-t border-slate-100 dark:border-slate-800"
                      >
                        <td className="py-3">{agency ? agency.name : link.agency_id}</td>
                        <td className="py-3">{code ? code.code : link.procedure_code_id}</td>
                        <td className="py-3">{link.policy_url}</td>
                        <td className="py-3">{link.status}</td>
                        <td className="py-3">{formatDateTime(link.updated_at)}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => openPolicyDialog(link)}
                              aria-label="Edit policy link"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => void handlePolicyDelete(link.id)}
                              aria-label="Delete policy link"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {!isLoading && policyLinks.length === 0 ? (
                    <tr>
                      <td className="py-6 text-center text-sm text-slate-500" colSpan={6}>
                        No policy links yet.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
