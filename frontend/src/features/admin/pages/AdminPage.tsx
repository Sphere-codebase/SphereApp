import { Pencil, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  createAdminUser,
  createAgency,
  createDiagnosis,
  createPolicyLink,
  createProcedureCode,
  deleteAgency,
  deleteDiagnosis,
  deletePolicyLink,
  deleteProcedureCode,
  getAdminClaimDetail,
  listAdminClaims,
  listAdminPatients,
  listAdminUsers,
  listAgencies,
  listDiagnoses,
  listPolicyLinks,
  listProcedureCodes,
  resetAdminUserPassword,
  updateAdminUser,
  updateAgency,
  updateDiagnosis,
  updatePolicyLink,
  updateProcedureCode,
  type AdminClaimDetail,
  type AdminClaimSummary,
  type AdminPatient,
  type AdminUser,
  type AdminUserCreateInput,
  type AdminUserUpdateInput,
  type Agency,
  type AgencyCreateInput,
  type Diagnosis,
  type DiagnosisCreateInput,
  type PolicyLink,
  type PolicyLinkCreateInput,
  type ProcedureCode,
} from "@/features/admin/api/client";
import type { ClaimStatus } from "@/features/admin/api/schemas";
import DataTable from "@/features/admin/components/DataTable";
import EditDialog from "@/features/admin/components/EditDialog";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import { cn } from "@/lib/utils";

type AdminTab = "reference" | "agencies" | "dashboard" | "users";
type ReferenceTab = "procedure-codes" | "diagnoses";

type AgencyFormState = {
  name: string;
  is_active: boolean;
};

type ProcedureCodeFormState = {
  code: string;
  title: string;
};

type DiagnosisFormState = {
  code: string;
  title: string;
};

type PolicyFormState = {
  agency_id: string;
  procedure_code_id: string;
  procedure_code_label: string;
  policy_url: string;
  effective_from: string;
  effective_to: string;
  status: "ACTIVE" | "INACTIVE";
  notes: string;
};

type UserFormState = {
  email: string;
  full_name: string;
  password: string;
  is_admin: boolean;
  is_active: boolean;
};

type ResetPasswordState = {
  password: string;
};

type ClaimsFilters = {
  patient_id: string;
  agency_id: string;
  status: "" | ClaimStatus;
  service_from: string;
  service_to: string;
};

const emptyAgencyForm: AgencyFormState = {
  name: "",
  is_active: true,
};

const emptyProcedureForm: ProcedureCodeFormState = {
  code: "",
  title: "",
};

const emptyDiagnosisForm: DiagnosisFormState = {
  code: "",
  title: "",
};

const emptyPolicyForm: PolicyFormState = {
  agency_id: "",
  procedure_code_id: "",
  procedure_code_label: "",
  policy_url: "",
  effective_from: "",
  effective_to: "",
  status: "ACTIVE",
  notes: "",
};

const emptyUserForm: UserFormState = {
  email: "",
  full_name: "",
  password: "",
  is_admin: false,
  is_active: true,
};

const emptyResetForm: ResetPasswordState = {
  password: "",
};

const emptyClaimFilters: ClaimsFilters = {
  patient_id: "",
  agency_id: "",
  status: "",
  service_from: "",
  service_to: "",
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

function formatDateOnly(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleDateString();
}

export default function AdminPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<AdminTab>("reference");
  const [referenceTab, setReferenceTab] = useState<ReferenceTab>("procedure-codes");
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(false);

  const [agencies, setAgencies] = useState<Agency[]>([]);
  const [procedureCodes, setProcedureCodes] = useState<ProcedureCode[]>([]);
  const [diagnoses, setDiagnoses] = useState<Diagnosis[]>([]);
  const [policyLinks, setPolicyLinks] = useState<PolicyLink[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [patients, setPatients] = useState<AdminPatient[]>([]);
  const [claims, setClaims] = useState<AdminClaimSummary[]>([]);
  const [claimDetail, setClaimDetail] = useState<AdminClaimDetail | null>(null);

  const [selectedAgencyId, setSelectedAgencyId] = useState<string>("");
  const [claimsFilters, setClaimsFilters] =
    useState<ClaimsFilters>(emptyClaimFilters);
  const [policyFilters, setPolicyFilters] = useState({
    query: "",
    procedure_code_id: "",
  });

  const [agencyDialogOpen, setAgencyDialogOpen] = useState(false);
  const [procedureDialogOpen, setProcedureDialogOpen] = useState(false);
  const [diagnosisDialogOpen, setDiagnosisDialogOpen] = useState(false);
  const [policyDialogOpen, setPolicyDialogOpen] = useState(false);
  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [claimDialogOpen, setClaimDialogOpen] = useState(false);

  const [editingAgency, setEditingAgency] = useState<Agency | null>(null);
  const [editingProcedure, setEditingProcedure] = useState<ProcedureCode | null>(
    null
  );
  const [editingDiagnosis, setEditingDiagnosis] = useState<Diagnosis | null>(
    null
  );
  const [editingPolicy, setEditingPolicy] = useState<PolicyLink | null>(null);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);

  const [agencyForm, setAgencyForm] = useState<AgencyFormState>(emptyAgencyForm);
  const [procedureForm, setProcedureForm] =
    useState<ProcedureCodeFormState>(emptyProcedureForm);
  const [diagnosisForm, setDiagnosisForm] =
    useState<DiagnosisFormState>(emptyDiagnosisForm);
  const [policyForm, setPolicyForm] = useState<PolicyFormState>(emptyPolicyForm);
  const [userForm, setUserForm] = useState<UserFormState>(emptyUserForm);
  const [resetForm, setResetForm] = useState<ResetPasswordState>(emptyResetForm);
  const [userFormError, setUserFormError] = useState<string | null>(null);
  const [resetFormError, setResetFormError] = useState<string | null>(null);

  const agencyById = useMemo(
    () => new Map(agencies.map((agency) => [agency.id, agency])),
    [agencies]
  );

  const procedureCodeById = useMemo(
    () => new Map(procedureCodes.map((code) => [code.id, code])),
    [procedureCodes]
  );

  const procedureCodeByCode = useMemo(
    () => new Map(procedureCodes.map((code) => [code.code, code])),
    [procedureCodes]
  );

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
      const stillSelected = data.some((agency) => agency.id === selectedAgencyId);
      if (!stillSelected) {
        setSelectedAgencyId(data[0]?.id ?? "");
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError, selectedAgencyId]);

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

  const loadDiagnoses = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listDiagnoses();
      setDiagnoses(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError]);

  const loadPolicyLinks = useCallback(
    async (agencyId: string) => {
      if (!agencyId) {
        setPolicyLinks([]);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const filters: {
          agency_id: string;
          procedure_code_id?: string;
          query?: string;
        } = { agency_id: agencyId };
        if (policyFilters.procedure_code_id) {
          filters.procedure_code_id = policyFilters.procedure_code_id;
        }
        if (policyFilters.query) {
          filters.query = policyFilters.query;
        }
        const data = await listPolicyLinks(filters);
        setPolicyLinks(data);
      } catch (err) {
        handleApiError(err);
      } finally {
        setIsLoading(false);
      }
    },
    [handleApiError, policyFilters]
  );

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listAdminUsers({});
      setUsers(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError]);

  const loadPatients = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listAdminPatients();
      setPatients(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError]);

  const loadClaims = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const filters: {
        patient_id?: string;
        agency_id?: string;
        status?: string;
        service_from?: string;
        service_to?: string;
      } = {};
      if (claimsFilters.patient_id) {
        filters.patient_id = claimsFilters.patient_id;
      }
      if (claimsFilters.agency_id) {
        filters.agency_id = claimsFilters.agency_id;
      }
      if (claimsFilters.status) {
        filters.status = claimsFilters.status;
      }
      if (claimsFilters.service_from) {
        filters.service_from = claimsFilters.service_from;
      }
      if (claimsFilters.service_to) {
        filters.service_to = claimsFilters.service_to;
      }
      const data = await listAdminClaims(filters);
      setClaims(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [claimsFilters, handleApiError]);

  useEffect(() => {
    if (activeTab === "reference") {
      if (referenceTab === "procedure-codes") {
        void loadProcedureCodes();
      } else {
        void loadDiagnoses();
      }
    }
  }, [activeTab, referenceTab, loadDiagnoses, loadProcedureCodes]);

  useEffect(() => {
    if (activeTab === "agencies") {
      void loadAgencies();
      void loadProcedureCodes();
    }
  }, [activeTab, loadAgencies, loadProcedureCodes]);

  useEffect(() => {
    if (activeTab === "agencies" && selectedAgencyId) {
      void loadPolicyLinks(selectedAgencyId);
    }
  }, [activeTab, loadPolicyLinks, selectedAgencyId]);

  useEffect(() => {
    if (activeTab === "users") {
      void loadUsers();
    }
  }, [activeTab, loadUsers]);

  useEffect(() => {
    if (activeTab === "dashboard") {
      void loadPatients();
      void loadClaims();
    }
  }, [activeTab, loadClaims, loadPatients]);

  const openAgencyDialog = (agency: Agency | null) => {
    setEditingAgency(agency);
    setAgencyForm(
      agency
        ? {
            name: agency.name,
            is_active: agency.is_active,
          }
        : emptyAgencyForm
    );
    setAgencyDialogOpen(true);
  };

  const openProcedureDialog = (procedure: ProcedureCode | null) => {
    setEditingProcedure(procedure);
    setProcedureForm(
      procedure
        ? {
            code: procedure.code,
            title: procedure.title ?? "",
          }
        : emptyProcedureForm
    );
    setProcedureDialogOpen(true);
  };

  const openDiagnosisDialog = (diagnosis: Diagnosis | null) => {
    setEditingDiagnosis(diagnosis);
    setDiagnosisForm(
      diagnosis
        ? {
            code: diagnosis.code,
            title: diagnosis.title ?? "",
          }
        : emptyDiagnosisForm
    );
    setDiagnosisDialogOpen(true);
  };

  const openPolicyDialog = (policy: PolicyLink | null) => {
    setEditingPolicy(policy);
    const codeLabel = policy
      ? procedureCodeById.get(policy.procedure_code_id)?.code ?? ""
      : "";
    setPolicyForm(
      policy
        ? {
            agency_id: policy.agency_id,
            procedure_code_id: policy.procedure_code_id,
            procedure_code_label: codeLabel,
            policy_url: policy.policy_url,
            effective_from: formatDateInput(policy.effective_from),
            effective_to: formatDateInput(policy.effective_to),
            status: policy.status,
            notes: policy.notes ?? "",
          }
        : {
            ...emptyPolicyForm,
            agency_id: selectedAgencyId,
          }
    );
    setPolicyDialogOpen(true);
  };

  const openUserDialog = (target: AdminUser | null) => {
    setEditingUser(target);
    setUserFormError(null);
    setUserForm(
      target
        ? {
            email: target.email,
            full_name: target.full_name ?? "",
            password: "",
            is_admin: target.is_admin,
            is_active: target.is_active,
          }
        : emptyUserForm
    );
    setUserDialogOpen(true);
  };

  const openResetDialog = (target: AdminUser) => {
    setResetTarget(target);
    setResetFormError(null);
    setResetForm(emptyResetForm);
    setResetDialogOpen(true);
  };

  const handleAgencySubmit = async () => {
    setError(null);
    const payload: AgencyCreateInput = {
      name: agencyForm.name.trim(),
      is_active: agencyForm.is_active,
    };
    if (!payload.name) {
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

  const handleProcedureSubmit = async () => {
    setError(null);
    const payload = {
      code: procedureForm.code.trim(),
      title: procedureForm.title.trim() || null,
    };
    if (!payload.code) {
      return;
    }
    try {
      if (editingProcedure) {
        await updateProcedureCode(editingProcedure.id, payload);
      } else {
        await createProcedureCode(payload);
      }
      setProcedureDialogOpen(false);
      await loadProcedureCodes();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleDiagnosisSubmit = async () => {
    setError(null);
    const payload: DiagnosisCreateInput = {
      code: diagnosisForm.code.trim(),
      title: diagnosisForm.title.trim() || null,
    };
    if (!payload.code) {
      return;
    }
    try {
      if (editingDiagnosis) {
        await updateDiagnosis(editingDiagnosis.id, payload);
      } else {
        await createDiagnosis(payload);
      }
      setDiagnosisDialogOpen(false);
      await loadDiagnoses();
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
      effective_from: policyForm.effective_from || null,
      effective_to: policyForm.effective_to || null,
      status: policyForm.status,
      notes: policyForm.notes.trim() || null,
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
      await loadPolicyLinks(payload.agency_id);
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleAgencyDelete = async (agencyId: string) => {
    setError(null);
    try {
      await deleteAgency(agencyId);
      await loadAgencies();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleProcedureDelete = async (procedureId: string) => {
    setError(null);
    try {
      await deleteProcedureCode(procedureId);
      await loadProcedureCodes();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleDiagnosisDelete = async (diagnosisId: string) => {
    setError(null);
    try {
      await deleteDiagnosis(diagnosisId);
      await loadDiagnoses();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handlePolicyDelete = async (policyId: string) => {
    setError(null);
    try {
      await deletePolicyLink(policyId);
      await loadPolicyLinks(selectedAgencyId);
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleUserSubmit = async () => {
    setUserFormError(null);
    setError(null);
    const email = userForm.email.trim();
    const fullName = userForm.full_name.trim();
    if (!email) {
      setUserFormError("Email is required.");
      return;
    }
    if (!editingUser && !userForm.password.trim()) {
      setUserFormError("Password is required for new users.");
      return;
    }
    try {
      if (editingUser) {
        const payload: AdminUserUpdateInput = {
          email,
          full_name: fullName ? fullName : null,
          is_admin: userForm.is_admin,
          is_active: userForm.is_active,
        };
        await updateAdminUser(editingUser.id, payload);
      } else {
        const payload: AdminUserCreateInput = {
          email,
          full_name: fullName ? fullName : null,
          password: userForm.password.trim(),
          is_admin: userForm.is_admin,
          is_active: userForm.is_active,
        };
        await createAdminUser(payload);
      }
      setUserDialogOpen(false);
      setEditingUser(null);
      setUserForm(emptyUserForm);
      await loadUsers();
    } catch (err) {
      if (err instanceof ApiError) {
        setUserFormError(err.message);
      } else {
        setUserFormError("Unexpected error");
      }
      handleApiError(err);
    }
  };

  const handleResetPassword = async () => {
    if (!resetTarget) {
      return;
    }
    setResetFormError(null);
    setError(null);
    const password = resetForm.password.trim();
    if (!password) {
      setResetFormError("Password is required.");
      return;
    }
    try {
      await resetAdminUserPassword(resetTarget.id, { password });
      setResetDialogOpen(false);
      setResetTarget(null);
      setResetForm(emptyResetForm);
    } catch (err) {
      if (err instanceof ApiError) {
        setResetFormError(err.message);
      } else {
        setResetFormError("Unexpected error");
      }
      handleApiError(err);
    }
  };

  const handleUserToggle = async (target: AdminUser) => {
    setError(null);
    try {
      const updated = await updateAdminUser(target.id, {
        is_active: !target.is_active,
      });
      setUsers((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item))
      );
    } catch (err) {
      handleApiError(err);
    }
  };

  const openClaimDetail = async (claimId: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const detail = await getAdminClaimDetail(claimId);
      setClaimDetail(detail);
      setClaimDialogOpen(true);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleProcedureCodeInput = (value: string) => {
    const matched = procedureCodeByCode.get(value);
    setPolicyForm((prev) => ({
      ...prev,
      procedure_code_label: value,
      procedure_code_id: matched?.id ?? "",
    }));
  };

  const policyAgencyName = selectedAgencyId
    ? agencyById.get(selectedAgencyId)?.name ?? "Selected agency"
    : "Select an agency";

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Admin
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              Control Center
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {user?.email ?? "Admin"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/app/chat")}>
              Back to chat
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Logout
            </Button>
          </div>
        </header>

        <div className="flex flex-wrap gap-2">
          {(["reference", "agencies", "dashboard", "users"] as const).map((tab) => (
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
              {tab === "reference"
                ? "Reference"
                : tab === "agencies"
                  ? "Agencies & Policies"
                  : tab === "dashboard"
                    ? "Dashboard"
                    : "Users"}
            </button>
          ))}
        </div>

        {error ? <ErrorNotice error={error} /> : null}

        {activeTab === "reference" ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Reference</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  CPT codes and diagnoses lookup tables.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(["procedure-codes", "diagnoses"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    className={cn(
                      "rounded-full px-3 py-1 text-xs font-semibold",
                      referenceTab === tab
                        ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                        : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                    )}
                    onClick={() => setReferenceTab(tab)}
                  >
                    {tab === "procedure-codes" ? "Procedure Codes" : "Diagnoses"}
                  </button>
                ))}
              </div>
            </div>

            {referenceTab === "procedure-codes" ? (
              <div className="mt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
                    Procedure Codes
                  </h3>
                  <Button type="button" onClick={() => openProcedureDialog(null)}>
                    <Plus className="h-4 w-4" />
                    New code
                  </Button>
                </div>
                <DataTable
                  rows={procedureCodes}
                  emptyMessage={isLoading ? "Loading..." : "No procedure codes yet."}
                  getRowId={(row) => row.id}
                  columns={[
                    {
                      key: "code",
                      header: "Code",
                      cell: (row) => <span className="font-medium">{row.code}</span>,
                    },
                    {
                      key: "title",
                      header: "Title",
                      cell: (row) => row.title ?? "—",
                    },
                    {
                      key: "actions",
                      header: "",
                      cell: (row) => (
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => openProcedureDialog(row)}
                            aria-label={`Edit ${row.code}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            onClick={() => void handleProcedureDelete(row.id)}
                            aria-label={`Delete ${row.code}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ),
                      cellClassName: "text-right",
                      headerClassName: "text-right",
                    },
                  ]}
                />
              </div>
            ) : (
              <div className="mt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
                    Diagnoses
                  </h3>
                  <Button type="button" onClick={() => openDiagnosisDialog(null)}>
                    <Plus className="h-4 w-4" />
                    New diagnosis
                  </Button>
                </div>
                <DataTable
                  rows={diagnoses}
                  emptyMessage={isLoading ? "Loading..." : "No diagnoses yet."}
                  getRowId={(row) => row.id}
                  columns={[
                    {
                      key: "code",
                      header: "Code",
                      cell: (row) => <span className="font-medium">{row.code}</span>,
                    },
                    {
                      key: "title",
                      header: "Title",
                      cell: (row) => row.title ?? "—",
                    },
                    {
                      key: "actions",
                      header: "",
                      cell: (row) => (
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => openDiagnosisDialog(row)}
                            aria-label={`Edit ${row.code}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            onClick={() => void handleDiagnosisDelete(row.id)}
                            aria-label={`Delete ${row.code}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ),
                      cellClassName: "text-right",
                      headerClassName: "text-right",
                    },
                  ]}
                />
              </div>
            )}
          </section>
        ) : null}

        {activeTab === "agencies" ? (
          <section className="grid gap-6 lg:grid-cols-[280px_1fr]">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Agencies</h2>
                <Button type="button" onClick={() => openAgencyDialog(null)}>
                  <Plus className="h-4 w-4" />
                  New
                </Button>
              </div>
              <div className="mt-4 space-y-2">
                {agencies.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    {isLoading ? "Loading..." : "No agencies yet."}
                  </p>
                ) : (
                  agencies.map((agency) => (
                    <div
                      key={agency.id}
                      className={cn(
                        "flex w-full flex-col gap-2 rounded-2xl border px-3 py-2 text-left text-sm",
                        selectedAgencyId === agency.id
                          ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                          : "border-slate-200 bg-white text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                      )}
                      onClick={() => setSelectedAgencyId(agency.id)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{agency.name}</span>
                        <span className="text-xs">
                          {agency.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      <div className="text-xs opacity-70">{agency.slug}</div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={(event) => {
                            event.stopPropagation();
                            openAgencyDialog(agency);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleAgencyDelete(agency.id);
                          }}
                        >
                          Deactivate
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Policy Links</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {policyAgencyName}
                  </p>
                </div>
                <Button
                  type="button"
                  onClick={() => openPolicyDialog(null)}
                  disabled={!selectedAgencyId}
                >
                  <Plus className="h-4 w-4" />
                  New link
                </Button>
              </div>

              <div className="mt-4 flex flex-wrap gap-2 text-sm">
                <input
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  placeholder="Search policy links"
                  value={policyFilters.query}
                  onChange={(event) =>
                    setPolicyFilters((prev) => ({ ...prev, query: event.target.value }))
                  }
                />
                <select
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  value={policyFilters.procedure_code_id}
                  onChange={(event) =>
                    setPolicyFilters((prev) => ({
                      ...prev,
                      procedure_code_id: event.target.value,
                    }))
                  }
                >
                  <option value="">All codes</option>
                  {procedureCodes.map((code) => (
                    <option key={code.id} value={code.id}>
                      {code.code}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void loadPolicyLinks(selectedAgencyId)}
                >
                  Apply
                </Button>
              </div>

              <div className="mt-4">
                <DataTable
                  rows={policyLinks}
                  emptyMessage={isLoading ? "Loading..." : "No policy links yet."}
                  getRowId={(row) => row.id}
                  columns={[
                    {
                      key: "procedure",
                      header: "Procedure",
                      cell: (row) =>
                        procedureCodeById.get(row.procedure_code_id)?.code ?? "—",
                    },
                    {
                      key: "url",
                      header: "Policy URL",
                      cell: (row) => (
                        <a
                          href={row.policy_url}
                          className="text-slate-600 underline dark:text-slate-300"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {row.policy_url}
                        </a>
                      ),
                    },
                    {
                      key: "summary",
                      header: "Short summary",
                      cell: (row) => row.notes ?? "—",
                    },
                    {
                      key: "status",
                      header: "Status",
                      cell: (row) => row.status,
                    },
                    {
                      key: "actions",
                      header: "",
                      cell: (row) => (
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => openPolicyDialog(row)}
                            aria-label={`Edit policy ${row.id}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            onClick={() => void handlePolicyDelete(row.id)}
                            aria-label={`Delete policy ${row.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ),
                      cellClassName: "text-right",
                      headerClassName: "text-right",
                    },
                  ]}
                />
              </div>
            </div>
          </section>
        ) : null}

        {activeTab === "dashboard" ? (
          <section className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Patients</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Read-only list of tenant patients.
                  </p>
                </div>
                <Button type="button" variant="outline" onClick={() => void loadPatients()}>
                  Refresh
                </Button>
              </div>
              <div className="mt-4">
                <DataTable
                  rows={patients}
                  emptyMessage={isLoading ? "Loading..." : "No patients yet."}
                  getRowId={(row) => row.id}
                  columns={[
                    {
                      key: "name",
                      header: "Name",
                      cell: (row) => row.full_name,
                    },
                    {
                      key: "dob",
                      header: "DOB",
                      cell: (row) => formatDateOnly(row.date_of_birth),
                    },
                    {
                      key: "sex",
                      header: "Sex",
                      cell: (row) => row.sex ?? "—",
                    },
                    {
                      key: "owner",
                      header: "Doctor ID",
                      cell: (row) => row.user_id ?? "—",
                    },
                  ]}
                />
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Claims</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Read-only list with filters.
                  </p>
                </div>
                <Button type="button" variant="outline" onClick={() => void loadClaims()}>
                  Refresh
                </Button>
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-5">
                <input
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  placeholder="Patient ID"
                  value={claimsFilters.patient_id}
                  onChange={(event) =>
                    setClaimsFilters((prev) => ({
                      ...prev,
                      patient_id: event.target.value,
                    }))
                  }
                />
                <input
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  placeholder="Agency ID"
                  value={claimsFilters.agency_id}
                  onChange={(event) =>
                    setClaimsFilters((prev) => ({
                      ...prev,
                      agency_id: event.target.value,
                    }))
                  }
                />
                <select
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  value={claimsFilters.status}
                  onChange={(event) =>
                    setClaimsFilters((prev) => ({
                      ...prev,
                      status: event.target.value as ClaimsFilters["status"],
                    }))
                  }
                >
                  <option value="">All statuses</option>
                  <option value="DRAFT">Draft</option>
                  <option value="SUBMITTED">Submitted</option>
                  <option value="PAID">Paid</option>
                  <option value="DENIED">Denied</option>
                </select>
                <input
                  type="date"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  value={claimsFilters.service_from}
                  onChange={(event) =>
                    setClaimsFilters((prev) => ({
                      ...prev,
                      service_from: event.target.value,
                    }))
                  }
                />
                <input
                  type="date"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  value={claimsFilters.service_to}
                  onChange={(event) =>
                    setClaimsFilters((prev) => ({
                      ...prev,
                      service_to: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="mt-4">
                <DataTable
                  rows={claims}
                  emptyMessage={isLoading ? "Loading..." : "No claims yet."}
                  getRowId={(row) => row.id}
                  columns={[
                    {
                      key: "patient",
                      header: "Patient",
                      cell: (row) => row.patient_name,
                    },
                    {
                      key: "agency",
                      header: "Agency",
                      cell: (row) => row.agency_name ?? "—",
                    },
                    {
                      key: "status",
                      header: "Status",
                      cell: (row) => row.status,
                    },
                    {
                      key: "service",
                      header: "Service",
                      cell: (row) =>
                        row.service_from
                          ? formatDateOnly(row.service_from)
                          : "—",
                    },
                    {
                      key: "actions",
                      header: "",
                      cell: (row) => (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => void openClaimDetail(row.id)}
                        >
                          View
                        </Button>
                      ),
                      cellClassName: "text-right",
                      headerClassName: "text-right",
                    },
                  ]}
                />
              </div>
            </div>
          </section>
        ) : null}

        {activeTab === "users" ? (
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Users</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Manage admin and doctor accounts.
                </p>
              </div>
              <Button type="button" onClick={() => openUserDialog(null)}>
                <Plus className="h-4 w-4" />
                New user
              </Button>
            </div>

            <div className="mt-4">
              <DataTable
                rows={users}
                emptyMessage={isLoading ? "Loading..." : "No users yet."}
                getRowId={(row) => row.id}
                columns={[
                  {
                    key: "email",
                    header: "Email",
                    cell: (row) => row.email,
                  },
                  {
                    key: "name",
                    header: "Name",
                    cell: (row) => row.full_name ?? "—",
                  },
                  {
                    key: "role",
                    header: "Admin",
                    cell: (row) => (row.is_admin ? "Yes" : "No"),
                  },
                  {
                    key: "active",
                    header: "Active",
                    cell: (row) => (row.is_active ? "Yes" : "No"),
                  },
                  {
                    key: "actions",
                    header: "",
                    cell: (row) => (
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => openUserDialog(row)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => void handleUserToggle(row)}
                        >
                          {row.is_active ? "Disable" : "Enable"}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => openResetDialog(row)}
                        >
                          Reset PW
                        </Button>
                      </div>
                    ),
                    cellClassName: "text-right",
                    headerClassName: "text-right",
                  },
                ]}
              />
            </div>
          </section>
        ) : null}
      </div>

      <EditDialog
        open={agencyDialogOpen}
        onOpenChange={setAgencyDialogOpen}
        title={editingAgency ? "Edit agency" : "New agency"}
        description="Manage agency details."
        onSave={() => void handleAgencySubmit()}
      >
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
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={agencyForm.is_active}
            onChange={(event) =>
              setAgencyForm((prev) => ({ ...prev, is_active: event.target.checked }))
            }
          />
          Active
        </label>
      </EditDialog>

      <EditDialog
        open={procedureDialogOpen}
        onOpenChange={setProcedureDialogOpen}
        title={editingProcedure ? "Edit procedure code" : "New procedure code"}
        description="Manage CPT codes."
        onSave={() => void handleProcedureSubmit()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Code
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={procedureForm.code}
            onChange={(event) =>
              setProcedureForm((prev) => ({ ...prev, code: event.target.value }))
            }
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Title
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={procedureForm.title}
            onChange={(event) =>
              setProcedureForm((prev) => ({ ...prev, title: event.target.value }))
            }
          />
        </label>
      </EditDialog>

      <EditDialog
        open={diagnosisDialogOpen}
        onOpenChange={setDiagnosisDialogOpen}
        title={editingDiagnosis ? "Edit diagnosis" : "New diagnosis"}
        description="Manage ICD / diagnosis codes."
        onSave={() => void handleDiagnosisSubmit()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Code
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={diagnosisForm.code}
            onChange={(event) =>
              setDiagnosisForm((prev) => ({ ...prev, code: event.target.value }))
            }
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Title
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={diagnosisForm.title}
            onChange={(event) =>
              setDiagnosisForm((prev) => ({ ...prev, title: event.target.value }))
            }
          />
        </label>
      </EditDialog>

      <EditDialog
        open={policyDialogOpen}
        onOpenChange={setPolicyDialogOpen}
        title={editingPolicy ? "Edit policy link" : "New policy link"}
        description="Attach policy documentation to a CPT."
        onSave={() => void handlePolicySubmit()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Procedure code
          <input
            list="procedure-code-list"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={policyForm.procedure_code_label}
            onChange={(event) => handleProcedureCodeInput(event.target.value)}
            placeholder="Start typing CPT code"
          />
          <datalist id="procedure-code-list">
            {procedureCodes.map((code) => (
              <option key={code.id} value={code.code}>
                {code.code} {code.title ? `— ${code.title}` : ""}
              </option>
            ))}
          </datalist>
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
        <div className="grid gap-3 md:grid-cols-2">
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
                status: event.target.value as PolicyFormState["status"],
              }))
            }
          >
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Short summary
          <textarea
            className="min-h-[80px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={policyForm.notes}
            onChange={(event) =>
              setPolicyForm((prev) => ({ ...prev, notes: event.target.value }))
            }
          />
        </label>
      </EditDialog>

      <EditDialog
        open={userDialogOpen}
        onOpenChange={setUserDialogOpen}
        title={editingUser ? "Edit user" : "New user"}
        description="Create or update user accounts."
        onSave={() => void handleUserSubmit()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={userForm.email}
            onChange={(event) =>
              setUserForm((prev) => ({ ...prev, email: event.target.value }))
            }
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Full name
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={userForm.full_name}
            onChange={(event) =>
              setUserForm((prev) => ({ ...prev, full_name: event.target.value }))
            }
          />
        </label>
        {!editingUser ? (
          <label className="flex flex-col gap-1 text-sm">
            Password
            <input
              type="password"
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              value={userForm.password}
              onChange={(event) =>
                setUserForm((prev) => ({ ...prev, password: event.target.value }))
              }
            />
          </label>
        ) : null}
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={userForm.is_admin}
              onChange={(event) =>
                setUserForm((prev) => ({ ...prev, is_admin: event.target.checked }))
              }
            />
            Admin
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={userForm.is_active}
              onChange={(event) =>
                setUserForm((prev) => ({ ...prev, is_active: event.target.checked }))
              }
            />
            Active
          </label>
        </div>
        {userFormError ? (
          <p className="text-xs text-red-600 dark:text-red-300">{userFormError}</p>
        ) : null}
      </EditDialog>

      <EditDialog
        open={resetDialogOpen}
        onOpenChange={setResetDialogOpen}
        title="Reset password"
        description="Set a new temporary password for this user."
        onSave={() => void handleResetPassword()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            type="password"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={resetForm.password}
            onChange={(event) =>
              setResetForm((prev) => ({ ...prev, password: event.target.value }))
            }
          />
        </label>
        {resetFormError ? (
          <p className="text-xs text-red-600 dark:text-red-300">{resetFormError}</p>
        ) : null}
      </EditDialog>

      <Dialog
        open={claimDialogOpen}
        onOpenChange={(open) => {
          setClaimDialogOpen(open);
          if (!open) {
            setClaimDetail(null);
          }
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Claim details</DialogTitle>
            <DialogDescription>
              {claimDetail?.patient.full_name ?? "Patient"} ·{" "}
              {claimDetail?.status ?? "—"}
            </DialogDescription>
          </DialogHeader>
          {claimDetail ? (
            <div className="space-y-4 text-sm">
              <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                <h4 className="font-semibold">Totals</h4>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  <div>Billed: {claimDetail.billed_total_cents ?? "—"}</div>
                  <div>Allowed: {claimDetail.allowed_total_cents ?? "—"}</div>
                  <div>Paid: {claimDetail.paid_total_cents ?? "—"}</div>
                  <div>
                    Patient responsibility:{" "}
                    {claimDetail.patient_responsibility_cents ?? "—"}
                  </div>
                  <div>Received: {formatDateTime(claimDetail.received_at)}</div>
                  <div>Finalized: {formatDateTime(claimDetail.finalized_at)}</div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                <h4 className="font-semibold">Procedures</h4>
                {claimDetail.procedures.length === 0 ? (
                  <p className="mt-2 text-slate-500">No procedures.</p>
                ) : (
                  <div className="mt-2 space-y-3">
                    {claimDetail.procedures.map((procedure) => (
                      <div
                        key={procedure.id}
                        className="rounded-xl border border-slate-200 p-3 dark:border-slate-800"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-medium">
                            {procedure.procedure_code.code} ·{" "}
                            {procedure.procedure_code.title ?? "Procedure"}
                          </div>
                          <div>Units: {procedure.units}</div>
                        </div>
                        <div className="mt-2 grid gap-2 text-xs md:grid-cols-3">
                          <div>Billed: {procedure.billed_amount_cents ?? "—"}</div>
                          <div>Allowed: {procedure.allowed_amount_cents ?? "—"}</div>
                          <div>Paid: {procedure.paid_amount_cents ?? "—"}</div>
                          <div>Copay: {procedure.copay_amount_cents ?? "—"}</div>
                          <div>Deductible: {procedure.deductible_amount_cents ?? "—"}</div>
                          <div>Coinsurance: {procedure.coinsurance_amount_cents ?? "—"}</div>
                        </div>
                        {procedure.payments.length > 0 ? (
                          <div className="mt-3 space-y-1 text-xs">
                            <div className="font-semibold">Payments</div>
                            {procedure.payments.map((payment) => (
                              <div key={payment.id}>
                                {formatDateOnly(payment.paid_at)} ·{" "}
                                {payment.paid_amount_cents}{" "}
                                {payment.adjustment_reason_code
                                  ? `(${payment.adjustment_reason_code})`
                                  : ""}
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                <h4 className="font-semibold">Diagnoses</h4>
                {claimDetail.diagnoses.length === 0 ? (
                  <p className="mt-2 text-slate-500">No diagnoses.</p>
                ) : (
                  <ul className="mt-2 space-y-1 text-sm">
                    {claimDetail.diagnoses.map((diag) => (
                      <li key={diag.id}>
                        {diag.code} · {diag.title ?? "Diagnosis"}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Loading...</p>
          )}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => setClaimDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
