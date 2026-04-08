import { FileText, Pencil, Plus, RefreshCcw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Audit from "@/components/admin/organisms/Audit";
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
import WorkspaceTopBar from "@/components/workspace/WorkspaceTopBar";
import {
  createAdminUser,
  createDiagnosisCode,
  createInsuranceCompany,
  createMcpCode,
  createPolicyLink,
  deleteDiagnosisCode,
  deleteInsuranceCompany,
  deleteMcpCode,
  deletePolicyLink,
  getAdminClaimDetail,
  listAdminClaims,
  listAdminPatients,
  listAdminUsers,
  listDiagnosisCodes,
  listInsuranceCompanies,
  listMcpCodes,
  listPolicyLinks,
  parsePolicyLinkRules,
  resetAdminUserPassword,
  updateAdminUser,
  updateDiagnosisCode,
  updateInsuranceCompany,
  updateMcpCode,
  updatePolicyLink,
  type AdminClaimDetail,
  type AdminClaimSummary,
  type AdminPatient,
  type AdminUser,
  type AdminUserCreateInput,
  type AdminUserUpdateInput,
  type DiagnosisCode,
  type DiagnosisCodeCreateInput,
  type InsuranceCompany,
  type InsuranceCompanyCreateInput,
  type McpCode,
  type PolicyLink,
  type PolicyLinkCreateInput,
  type PolicyRulesParseProposed,
} from "@/features/admin/api/client";
import type { ClaimStatus } from "@/features/admin/api/schemas";
import DataTable from "@/features/admin/components/DataTable";
import EditDialog from "@/features/admin/components/EditDialog";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import { cn } from "@/lib/utils";
import Clinics from "@/components/admin/organisms/Clinics";

const tabs = [
  { name: "Dashboard", value: "dashboard" },
  { name: "Reference Data", value: "reference" },
  { name: "Companies", value: "companies" },
  { name: "Users", value: "users" },
  { name: "Audit", value: "audit" },
  { name: "Clinics", value: "clinics" },
];
type ReferenceTab = "mcp-codes" | "diagnosis-codes";

type InsuranceCompanyFormState = {
  name: string;
};

type McpCodeFormState = {
  code: string;
  description: string;
};

type DiagnosisCodeFormState = {
  code: string;
  description: string;
};

type PolicyFormState = {
  insurance_company_id: string;
  mcp_code: string;
  policy_url: string;
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
  insurance_company_id: string;
  status: "" | ClaimStatus;
  service_from: string;
  service_to: string;
};

const emptyCompanyForm: InsuranceCompanyFormState = {
  name: "",
};

const emptyMcpForm: McpCodeFormState = {
  code: "",
  description: "",
};

const emptyDiagnosisForm: DiagnosisCodeFormState = {
  code: "",
  description: "",
};

const emptyPolicyForm: PolicyFormState = {
  insurance_company_id: "",
  mcp_code: "",
  policy_url: "",
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
  insurance_company_id: "",
  status: "",
  service_from: "",
  service_to: "",
};

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
  const { me, logout, hasRole } = useAuth();
  const isAdmin = me?.role === "platform_staff_admin";
  const [activeTab, setActiveTab] = useState<string>("reference");
  const [referenceTab, setReferenceTab] = useState<ReferenceTab>("mcp-codes");
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(false);

  const [companies, setCompanies] = useState<InsuranceCompany[]>([]);
  const [mcpCodes, setMcpCodes] = useState<McpCode[]>([]);
  const [diagnosisCodes, setDiagnosisCodes] = useState<DiagnosisCode[]>([]);
  const [policyLinks, setPolicyLinks] = useState<PolicyLink[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [patients, setPatients] = useState<AdminPatient[]>([]);
  const [claims, setClaims] = useState<AdminClaimSummary[]>([]);
  const [claimDetail, setClaimDetail] = useState<AdminClaimDetail | null>(null);
  const [policyRefreshDialogOpen, setPolicyRefreshDialogOpen] = useState(false);
  const [policyRefreshTarget, setPolicyRefreshTarget] = useState<PolicyLink | null>(null);
  const [policyRefreshProposed, setPolicyRefreshProposed] =
    useState<PolicyRulesParseProposed | null>(null);
  const [policyRefreshLoading, setPolicyRefreshLoading] = useState(false);

  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [claimsFilters, setClaimsFilters] = useState<ClaimsFilters>(emptyClaimFilters);
  const [policyFilters, setPolicyFilters] = useState({
    query: "",
    mcp_code: "",
  });

  const [companyDialogOpen, setCompanyDialogOpen] = useState(false);
  const [mcpDialogOpen, setMcpDialogOpen] = useState(false);
  const [diagnosisDialogOpen, setDiagnosisDialogOpen] = useState(false);
  const [policyDialogOpen, setPolicyDialogOpen] = useState(false);
  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [claimDialogOpen, setClaimDialogOpen] = useState(false);

  const [editingCompany, setEditingCompany] = useState<InsuranceCompany | null>(null);
  const [editingMcp, setEditingMcp] = useState<McpCode | null>(null);
  const [editingDiagnosis, setEditingDiagnosis] = useState<DiagnosisCode | null>(null);
  const [editingPolicy, setEditingPolicy] = useState<PolicyLink | null>(null);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);

  const [companyForm, setCompanyForm] =
    useState<InsuranceCompanyFormState>(emptyCompanyForm);
  const [mcpForm, setMcpForm] = useState<McpCodeFormState>(emptyMcpForm);
  const [diagnosisForm, setDiagnosisForm] =
    useState<DiagnosisCodeFormState>(emptyDiagnosisForm);
  const [policyForm, setPolicyForm] = useState<PolicyFormState>(emptyPolicyForm);
  const [userForm, setUserForm] = useState<UserFormState>(emptyUserForm);
  const [resetForm, setResetForm] = useState<ResetPasswordState>(emptyResetForm);
  const [userFormError, setUserFormError] = useState<string | null>(null);
  const [resetFormError, setResetFormError] = useState<string | null>(null);

  const companyById = useMemo(
    () => new Map(companies.map((company) => [company.id, company])),
    [companies]
  );

  const mcpCodeByCode = useMemo(
    () => new Map(mcpCodes.map((code) => [code.code, code])),
    [mcpCodes]
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

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const loadCompanies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listInsuranceCompanies();
      setCompanies(data);
      const stillSelected = data.some(
        (company) => String(company.id) === selectedCompanyId
      );
      if (!stillSelected) {
        setSelectedCompanyId(data[0] ? String(data[0].id) : "");
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError, selectedCompanyId]);

  const loadMcpCodes = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listMcpCodes();
      setMcpCodes(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError]);

  const loadDiagnosisCodes = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listDiagnosisCodes();
      setDiagnosisCodes(data);
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoading(false);
    }
  }, [handleApiError]);

  const loadPolicyLinks = useCallback(
    async (companyId: string) => {
      if (!companyId) {
        setPolicyLinks([]);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const filters: {
          insurance_company_id: number;
          mcp_code?: string;
          query?: string;
        } = { insurance_company_id: Number(companyId) };
        if (policyFilters.mcp_code) {
          filters.mcp_code = policyFilters.mcp_code;
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
        patient_id?: number;
        insurance_company_id?: number;
        status?: string;
        service_from?: string;
        service_to?: string;
      } = {};
      if (claimsFilters.patient_id) {
        filters.patient_id = Number(claimsFilters.patient_id);
      }
      if (claimsFilters.insurance_company_id) {
        filters.insurance_company_id = Number(claimsFilters.insurance_company_id);
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
      if (referenceTab === "mcp-codes") {
        void loadMcpCodes();
      } else {
        void loadDiagnosisCodes();
      }
    }
  }, [activeTab, referenceTab, loadDiagnosisCodes, loadMcpCodes]);

  useEffect(() => {
    if (activeTab === "companies") {
      void loadCompanies();
      void loadMcpCodes();
    }
  }, [activeTab, loadCompanies, loadMcpCodes]);

  useEffect(() => {
    if (activeTab === "companies" && selectedCompanyId) {
      void loadPolicyLinks(selectedCompanyId);
    }
  }, [activeTab, loadPolicyLinks, selectedCompanyId]);

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

  const openCompanyDialog = (company: InsuranceCompany | null) => {
    setEditingCompany(company);
    setCompanyForm(
      company
        ? {
            name: company.name,
          }
        : emptyCompanyForm
    );
    setCompanyDialogOpen(true);
  };

  const openMcpDialog = (code: McpCode | null) => {
    setEditingMcp(code);
    setMcpForm(
      code
        ? {
            code: code.code,
            description: code.description ?? "",
          }
        : emptyMcpForm
    );
    setMcpDialogOpen(true);
  };

  const openDiagnosisDialog = (diagnosis: DiagnosisCode | null) => {
    setEditingDiagnosis(diagnosis);
    setDiagnosisForm(
      diagnosis
        ? {
            code: diagnosis.code,
            description: diagnosis.description ?? "",
          }
        : emptyDiagnosisForm
    );
    setDiagnosisDialogOpen(true);
  };

  const openPolicyDialog = (policy: PolicyLink | null) => {
    setEditingPolicy(policy);
    setPolicyForm(
      policy
        ? {
            insurance_company_id: String(policy.insurance_company_id),
            mcp_code: policy.mcp_code,
            policy_url: policy.policy_url,
          }
        : {
            ...emptyPolicyForm,
            insurance_company_id: selectedCompanyId,
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
            is_admin: target.roles.includes("platform_staff_admin"),
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

  const handleCompanySubmit = async () => {
    setError(null);
    const payload: InsuranceCompanyCreateInput = {
      name: companyForm.name.trim(),
    };
    if (!payload.name) {
      return;
    }
    try {
      if (editingCompany) {
        await updateInsuranceCompany(editingCompany.id, payload);
      } else {
        await createInsuranceCompany(payload);
      }
      setCompanyDialogOpen(false);
      await loadCompanies();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleMcpSubmit = async () => {
    setError(null);
    const payload = {
      code: mcpForm.code.trim(),
      description: mcpForm.description.trim() || null,
    };
    if (!payload.code) {
      return;
    }
    try {
      if (editingMcp) {
        await updateMcpCode(editingMcp.code, { description: payload.description });
      } else {
        await createMcpCode(payload);
      }
      setMcpDialogOpen(false);
      await loadMcpCodes();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleDiagnosisSubmit = async () => {
    setError(null);
    const payload: DiagnosisCodeCreateInput = {
      code: diagnosisForm.code.trim(),
      description: diagnosisForm.description.trim() || null,
    };
    if (!payload.code) {
      return;
    }
    try {
      if (editingDiagnosis) {
        await updateDiagnosisCode(editingDiagnosis.code, payload);
      } else {
        await createDiagnosisCode(payload);
      }
      setDiagnosisDialogOpen(false);
      await loadDiagnosisCodes();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handlePolicySubmit = async () => {
    setError(null);
    const payload: PolicyLinkCreateInput = {
      insurance_company_id: Number(policyForm.insurance_company_id),
      mcp_code: policyForm.mcp_code.trim(),
      policy_url: policyForm.policy_url.trim(),
    };
    if (!payload.insurance_company_id || !payload.mcp_code || !payload.policy_url) {
      return;
    }
    try {
      if (editingPolicy) {
        await updatePolicyLink(editingPolicy.id, payload);
      } else {
        await createPolicyLink(payload);
      }
      setPolicyDialogOpen(false);
      await loadPolicyLinks(String(payload.insurance_company_id));
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleCompanyDelete = async (companyId: number) => {
    setError(null);
    try {
      await deleteInsuranceCompany(companyId);
      await loadCompanies();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleMcpDelete = async (code: string) => {
    setError(null);
    try {
      await deleteMcpCode(code);
      await loadMcpCodes();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handleDiagnosisDelete = async (code: string) => {
    setError(null);
    try {
      await deleteDiagnosisCode(code);
      await loadDiagnosisCodes();
    } catch (err) {
      handleApiError(err);
    }
  };

  const handlePolicyDelete = async (policyId: number) => {
    setError(null);
    try {
      await deletePolicyLink(policyId);
      await loadPolicyLinks(selectedCompanyId);
    } catch (err) {
      handleApiError(err);
    }
  };

  const handlePolicyRulesRefresh = async (policy: PolicyLink) => {
    setError(null);
    setPolicyRefreshLoading(true);
    setPolicyRefreshTarget(policy);
    setPolicyRefreshProposed(null);
    try {
      const result = await parsePolicyLinkRules(policy.id, false);
      if ("action_required" in result) {
        setPolicyRefreshProposed(result.proposed_changes);
        setPolicyRefreshDialogOpen(true);
        return;
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setPolicyRefreshLoading(false);
    }
  };

  const handlePolicyRulesConfirm = async () => {
    if (!policyRefreshTarget) {
      return;
    }
    setError(null);
    setPolicyRefreshLoading(true);
    try {
      const result = await parsePolicyLinkRules(policyRefreshTarget.id, true);
      if ("status" in result) {
        setPolicyRefreshDialogOpen(false);
        setPolicyRefreshProposed(null);
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setPolicyRefreshLoading(false);
    }
  };

  const openPolicyRulesPage = useCallback(
    (policy: PolicyLink) => {
      const params = new URLSearchParams({
        mcp_code: policy.mcp_code,
        policy_link_id: String(policy.id),
      });
      navigate(`/app/admin/policy-rules?${params.toString()}`);
    },
    [navigate]
  );

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
          roles: userForm.is_admin ? ["platform_staff_admin"] : [],
          is_active: userForm.is_active,
        };
        await updateAdminUser(editingUser.id, payload);
      } else {
        const payload: AdminUserCreateInput = {
          email,
          full_name: fullName ? fullName : null,
          password: userForm.password.trim(),
          roles: userForm.is_admin ? ["platform_staff_admin"] : [],
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
      setUsers((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      handleApiError(err);
    }
  };

  const openClaimDetail = async (claimId: number) => {
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

  const handleMcpCodeInput = (value: string) => {
    setPolicyForm((prev) => ({
      ...prev,
      mcp_code: value,
    }));
  };

  const policyCompanyName = selectedCompanyId
    ? (companyById.get(Number(selectedCompanyId))?.name ?? "Selected company")
    : "Select a company";

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-8">
        <WorkspaceTopBar
          title="Admin"
          subtitle={me?.clinic_name ?? "Clinic"}
          isSending={false}
          showAdmin={hasRole(["platform_staff_admin", "clinic_admin", "chief_doctor"])}
          claimStatus={null}
          onLogout={handleUnauthorized}
        />

        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.value}
              type="button"
              className={cn(
                "rounded-full px-4 py-2 text-sm font-medium",
                activeTab === tab.value
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "bg-white text-slate-600 shadow-sm dark:bg-slate-900 dark:text-slate-300"
              )}
              onClick={() => setActiveTab(tab.value)}
            >
              {tab.name}
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
                  MCP codes and diagnosis lookup tables.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(["mcp-codes", "diagnosis-codes"] as const).map((tab) => (
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
                    {tab === "mcp-codes" ? "MCP Codes" : "Diagnosis Codes"}
                  </button>
                ))}
              </div>
            </div>

            {referenceTab === "mcp-codes" ? (
              <div className="mt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
                    MCP Codes
                  </h3>
                  <Button type="button" onClick={() => openMcpDialog(null)}>
                    <Plus className="h-4 w-4" />
                    New code
                  </Button>
                </div>
                <DataTable
                  rows={mcpCodes}
                  emptyMessage={isLoading ? "Loading..." : "No MCP codes yet."}
                  getRowId={(row) => row.code}
                  columns={[
                    {
                      key: "code",
                      header: "Code",
                      cell: (row) => <span className="font-medium">{row.code}</span>,
                    },
                    {
                      key: "description",
                      header: "Description",
                      cell: (row) => row.description ?? "—",
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
                            onClick={() => openMcpDialog(row)}
                            aria-label={`Edit ${row.code}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            onClick={() => void handleMcpDelete(row.code)}
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
                    Diagnosis codes
                  </h3>
                  <Button type="button" onClick={() => openDiagnosisDialog(null)}>
                    <Plus className="h-4 w-4" />
                    New diagnosis
                  </Button>
                </div>
                <DataTable
                  rows={diagnosisCodes}
                  emptyMessage={isLoading ? "Loading..." : "No diagnosis codes yet."}
                  getRowId={(row) => row.code}
                  columns={[
                    {
                      key: "code",
                      header: "Code",
                      cell: (row) => <span className="font-medium">{row.code}</span>,
                    },
                    {
                      key: "description",
                      header: "Description",
                      cell: (row) => row.description ?? "—",
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
                            onClick={() => void handleDiagnosisDelete(row.code)}
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

        {activeTab === "companies" ? (
          <section className="grid gap-6 lg:grid-cols-[280px_1fr]">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Insurance companies</h2>
                <Button type="button" onClick={() => openCompanyDialog(null)}>
                  <Plus className="h-4 w-4" />
                  New
                </Button>
              </div>
              <div className="mt-4 space-y-2">
                {companies.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    {isLoading ? "Loading..." : "No companies yet."}
                  </p>
                ) : (
                  companies.map((company) => (
                    <div
                      key={company.id}
                      className={cn(
                        "flex w-full flex-col gap-2 rounded-2xl border px-3 py-2 text-left text-sm",
                        selectedCompanyId === String(company.id)
                          ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                          : "border-slate-200 bg-white text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200"
                      )}
                      onClick={() => setSelectedCompanyId(String(company.id))}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{company.name}</span>
                        <span className="text-xs">
                          {formatDateOnly(company.created_at)}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={(event) => {
                            event.stopPropagation();
                            openCompanyDialog(company);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleCompanyDelete(company.id);
                          }}
                        >
                          Delete
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
                    {policyCompanyName}
                  </p>
                </div>
                <Button
                  type="button"
                  onClick={() => openPolicyDialog(null)}
                  disabled={!selectedCompanyId}
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
                  value={policyFilters.mcp_code}
                  onChange={(event) =>
                    setPolicyFilters((prev) => ({
                      ...prev,
                      mcp_code: event.target.value,
                    }))
                  }
                >
                  <option value="">All codes</option>
                  {mcpCodes.map((code) => (
                    <option key={code.code} value={code.code}>
                      {code.code}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void loadPolicyLinks(selectedCompanyId)}
                >
                  Apply
                </Button>
              </div>

              <div className="mt-4">
                <DataTable
                  rows={policyLinks}
                  emptyMessage={isLoading ? "Loading..." : "No policy links yet."}
                  getRowId={(row) => String(row.id)}
                  columns={[
                    {
                      key: "mcp",
                      header: "MCP code",
                      cell: (row) => row.mcp_code,
                    },
                    {
                      key: "description",
                      header: "Description",
                      cell: (row) => mcpCodeByCode.get(row.mcp_code)?.description ?? "—",
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
                      key: "created",
                      header: "Added",
                      cell: (row) => formatDateOnly(row.created_at),
                    },
                    {
                      key: "actions",
                      header: "",
                      cell: (row) => (
                        <div className="flex items-center justify-end gap-2">
                          {isAdmin ? (
                            <>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => void handlePolicyRulesRefresh(row)}
                                aria-label={`Refresh rules for policy ${row.id}`}
                                disabled={
                                  policyRefreshLoading &&
                                  policyRefreshTarget?.id === row.id
                                }
                              >
                                <RefreshCcw className="h-4 w-4" />
                                Refresh Rules
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => openPolicyRulesPage(row)}
                                aria-label={`View rules for policy ${row.id}`}
                              >
                                <FileText className="h-4 w-4" />
                                View Rules
                              </Button>
                            </>
                          ) : null}
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
                    Read-only list of patients.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void loadPatients()}
                >
                  Refresh
                </Button>
              </div>
              <div className="mt-4">
                <DataTable
                  rows={patients}
                  emptyMessage={isLoading ? "Loading..." : "No patients yet."}
                  getRowId={(row) => String(row.id)}
                  columns={[
                    {
                      key: "name",
                      header: "Name",
                      cell: (row) => {
                        const name =
                          `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim();
                        return name || "—";
                      },
                    },
                    {
                      key: "dob",
                      header: "DOB",
                      cell: (row) => formatDateOnly(row.date_of_birth),
                    },
                    {
                      key: "owner",
                      header: "Doctor ID",
                      cell: (row) => row.doctor_id,
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
                  placeholder="Company ID"
                  value={claimsFilters.insurance_company_id}
                  onChange={(event) =>
                    setClaimsFilters((prev) => ({
                      ...prev,
                      insurance_company_id: event.target.value,
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
                  getRowId={(row) => String(row.id)}
                  columns={[
                    {
                      key: "patient",
                      header: "Patient",
                      cell: (row) => row.patient_name,
                    },
                    {
                      key: "company",
                      header: "Company",
                      cell: (row) => row.insurance_company_name ?? "—",
                    },
                    {
                      key: "status",
                      header: "Status",
                      cell: (row) => row.claim_status ?? "—",
                    },
                    {
                      key: "service",
                      header: "Service",
                      cell: (row) =>
                        row.service_date ? formatDateOnly(row.service_date) : "—",
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
                getRowId={(row) => String(row.id)}
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
                    cell: (row) =>
                      row.roles.includes("platform_staff_admin") ? "Yes" : "No",
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
        {activeTab === "audit" ? <Audit /> : null}
        {activeTab === "clinics" ? <Clinics /> : null}
      </div>

      <EditDialog
        open={companyDialogOpen}
        onOpenChange={setCompanyDialogOpen}
        title={editingCompany ? "Edit company" : "New company"}
        description="Manage insurance company details."
        onSave={() => void handleCompanySubmit()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Name
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={companyForm.name}
            onChange={(event) =>
              setCompanyForm((prev) => ({ ...prev, name: event.target.value }))
            }
          />
        </label>
      </EditDialog>

      <EditDialog
        open={mcpDialogOpen}
        onOpenChange={setMcpDialogOpen}
        title={editingMcp ? "Edit MCP code" : "New MCP code"}
        description="Manage MCP codes."
        onSave={() => void handleMcpSubmit()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Code
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={mcpForm.code}
            onChange={(event) =>
              setMcpForm((prev) => ({ ...prev, code: event.target.value }))
            }
            disabled={Boolean(editingMcp)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Description
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={mcpForm.description}
            onChange={(event) =>
              setMcpForm((prev) => ({ ...prev, description: event.target.value }))
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
          Description
          <input
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={diagnosisForm.description}
            onChange={(event) =>
              setDiagnosisForm((prev) => ({
                ...prev,
                description: event.target.value,
              }))
            }
          />
        </label>
      </EditDialog>

      <EditDialog
        open={policyDialogOpen}
        onOpenChange={setPolicyDialogOpen}
        title={editingPolicy ? "Edit policy link" : "New policy link"}
        description="Attach policy documentation to an MCP code."
        onSave={() => void handlePolicySubmit()}
      >
        <label className="flex flex-col gap-1 text-sm">
          Insurance company
          <select
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={policyForm.insurance_company_id}
            onChange={(event) =>
              setPolicyForm((prev) => ({
                ...prev,
                insurance_company_id: event.target.value,
              }))
            }
          >
            <option value="">Select a company</option>
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          MCP code
          <input
            list="mcp-code-list"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            value={policyForm.mcp_code}
            onChange={(event) => handleMcpCodeInput(event.target.value)}
            placeholder="Start typing MCP code"
          />
          <datalist id="mcp-code-list">
            {mcpCodes.map((code) => (
              <option key={code.code} value={code.code}>
                {code.code} {code.description ? `— ${code.description}` : ""}
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
      </EditDialog>

      <Dialog
        open={policyRefreshDialogOpen}
        onOpenChange={(open) => {
          setPolicyRefreshDialogOpen(open);
          if (!open) {
            setPolicyRefreshProposed(null);
            setPolicyRefreshTarget(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Refresh policy rules</DialogTitle>
            <DialogDescription>
              Review extracted policy details before storing.
            </DialogDescription>
          </DialogHeader>
          {policyRefreshProposed ? (
            <div className="space-y-3 text-sm text-slate-700 dark:text-slate-200">
              <div>
                <div className="text-xs uppercase text-slate-400">Title</div>
                <div className="font-medium">{policyRefreshProposed.title ?? "—"}</div>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                <div>
                  <div className="text-xs uppercase text-slate-400">Next review</div>
                  <div>{formatDateOnly(policyRefreshProposed.next_review_iso)}</div>
                </div>
                <div>
                  <div className="text-xs uppercase text-slate-400">Criteria</div>
                  <div>{policyRefreshProposed.criteria_count}</div>
                </div>
                <div>
                  <div className="text-xs uppercase text-slate-400">Notes</div>
                  <div>{policyRefreshProposed.notes_count}</div>
                </div>
              </div>
              <div>
                <div className="text-xs uppercase text-slate-400">
                  Medical necessity (preview)
                </div>
                <div className="max-h-32 overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
                  {policyRefreshProposed.medical_necessity_clean_preview}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Preparing policy rules...</p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setPolicyRefreshDialogOpen(false)}
              disabled={policyRefreshLoading}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void handlePolicyRulesConfirm()}
              disabled={policyRefreshLoading}
            >
              Confirm refresh
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
            Platform admin
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
              {claimDetail
                ? `${claimDetail.patient.first_name ?? ""} ${claimDetail.patient.last_name ?? ""}`.trim() ||
                  "Patient"
                : "Patient"}{" "}
              · {claimDetail?.claim_status ?? "—"}
            </DialogDescription>
          </DialogHeader>
          {claimDetail ? (
            <div className="space-y-4 text-sm">
              <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                <h4 className="font-semibold">Totals</h4>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  <div>Billed: {claimDetail.billed_amount_total ?? "—"}</div>
                  <div>Allowed: {claimDetail.allowed_amount_total ?? "—"}</div>
                  <div>Coinsurance: {claimDetail.coinsurance_amount_total ?? "—"}</div>
                  <div>Copay: {claimDetail.copay_amount_total ?? "—"}</div>
                  <div>Deductible: {claimDetail.deductible_amount_total ?? "—"}</div>
                  <div>Claim date: {formatDateOnly(claimDetail.claim_date)}</div>
                  <div>Service date: {formatDateOnly(claimDetail.service_date)}</div>
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
                            {procedure.mcp_code.code} ·{" "}
                            {procedure.mcp_code.description ?? "Procedure"}
                          </div>
                          <div>Units: {procedure.units ?? "—"}</div>
                        </div>
                        <div className="mt-2 grid gap-2 text-xs md:grid-cols-3">
                          <div>Billed: {procedure.billed_amount ?? "—"}</div>
                          <div>Allowed: {procedure.allowed_amount ?? "—"}</div>
                          <div>Paid: {procedure.paid_amount ?? "—"}</div>
                          <div>Copay: {procedure.copay_amount ?? "—"}</div>
                          <div>Deductible: {procedure.deductible_amount ?? "—"}</div>
                          <div>Coinsurance: {procedure.coinsurance_amount ?? "—"}</div>
                        </div>
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
                      <li key={diag.code}>
                        {diag.code} · {diag.description ?? "Diagnosis"}
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
            <Button
              type="button"
              variant="secondary"
              onClick={() => setClaimDialogOpen(false)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
