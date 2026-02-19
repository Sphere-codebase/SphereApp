import { ArrowLeft, FileText, RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

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
  getPolicyLinkRules,
  listInsuranceCompanies,
  listMcpCodes,
  listPolicyLinks,
  parsePolicyLinkRules,
  type InsuranceCompany,
  type McpCode,
  type PolicyLink,
  type PolicyRule,
  type PolicyRulesParseProposed,
} from "@/features/admin/api/client";
import DataTable from "@/features/admin/components/DataTable";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";
import { cn } from "@/lib/utils";

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

export default function PolicyRulesPage() {
  const navigate = useNavigate();
  const { me, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialMcpCode = searchParams.get("mcp_code") ?? "";
  const initialPolicyLinkIdParam = searchParams.get("policy_link_id");
  const initialPolicyLinkId = initialPolicyLinkIdParam
    ? Number(initialPolicyLinkIdParam)
    : null;

  const [error, setError] = useState<unknown>(null);
  const [mcpCodes, setMcpCodes] = useState<McpCode[]>([]);
  const [companies, setCompanies] = useState<InsuranceCompany[]>([]);
  const [policyLinks, setPolicyLinks] = useState<PolicyLink[]>([]);
  const [policyLinksLoading, setPolicyLinksLoading] = useState(false);
  const [selectedMcpCode, setSelectedMcpCode] = useState(initialMcpCode);
  const [selectedPolicyLinkId, setSelectedPolicyLinkId] =
    useState<number | null>(initialPolicyLinkId);
  const initialPolicyLinkIdRef = useRef<number | null>(initialPolicyLinkId);
  const [policyRules, setPolicyRules] = useState<PolicyRule | null>(null);
  const [policyRulesLoading, setPolicyRulesLoading] = useState(false);
  const [policyRulesError, setPolicyRulesError] = useState<string | null>(null);

  const [policyRefreshDialogOpen, setPolicyRefreshDialogOpen] = useState(false);
  const [policyRefreshProposed, setPolicyRefreshProposed] =
    useState<PolicyRulesParseProposed | null>(null);
  const [policyRefreshLoading, setPolicyRefreshLoading] = useState(false);

  const companyById = useMemo(
    () => new Map(companies.map((company) => [company.id, company])),
    [companies]
  );

  const selectedPolicyLink = useMemo(() => {
    if (!selectedPolicyLinkId) {
      return null;
    }
    return policyLinks.find((link) => link.id === selectedPolicyLinkId) ?? null;
  }, [policyLinks, selectedPolicyLinkId]);

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

  const updateSearchParams = useCallback(
    (mcpCode: string, policyLinkId: number | null) => {
      const next = new URLSearchParams();
      if (mcpCode) {
        next.set("mcp_code", mcpCode);
      }
      if (policyLinkId) {
        next.set("policy_link_id", String(policyLinkId));
      }
      setSearchParams(next, { replace: true });
    },
    [setSearchParams]
  );

  const loadMcpCodes = useCallback(async () => {
    setError(null);
    try {
      const data = await listMcpCodes();
      setMcpCodes(data);
    } catch (err) {
      handleApiError(err);
    }
  }, [handleApiError]);

  const loadCompanies = useCallback(async () => {
    setError(null);
    try {
      const data = await listInsuranceCompanies();
      setCompanies(data);
    } catch (err) {
      handleApiError(err);
    }
  }, [handleApiError]);

  const loadPolicyLinks = useCallback(
    async (mcpCode: string, keepPolicyLinkId: number | null) => {
      if (!mcpCode) {
        setPolicyLinks([]);
        setSelectedPolicyLinkId(null);
        setPolicyRules(null);
        setPolicyRulesError(null);
        return;
      }
      setPolicyLinksLoading(true);
      setPolicyRules(null);
      setPolicyRulesError(null);
      setSelectedPolicyLinkId(null);
      setError(null);
      try {
        const data = await listPolicyLinks({ mcp_code: mcpCode });
        setPolicyLinks(data);
        const current = data.find((link) => link.id === keepPolicyLinkId);
        const nextId = current?.id ?? data[0]?.id ?? null;
        setSelectedPolicyLinkId(nextId);
      } catch (err) {
        handleApiError(err);
      } finally {
        setPolicyLinksLoading(false);
      }
    },
    [handleApiError]
  );

  const loadPolicyRules = useCallback(
    async (policyLinkId: number) => {
      setPolicyRulesLoading(true);
      setPolicyRulesError(null);
      try {
        const data = await getPolicyLinkRules(policyLinkId);
        setPolicyRules(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setPolicyRules(null);
          setPolicyRulesError(null);
        } else {
          if (err instanceof ApiError) {
            setPolicyRulesError(err.message);
          }
          handleApiError(err);
        }
      } finally {
        setPolicyRulesLoading(false);
      }
    },
    [handleApiError]
  );

  useEffect(() => {
    void loadMcpCodes();
    void loadCompanies();
  }, [loadCompanies, loadMcpCodes]);

  useEffect(() => {
    void loadPolicyLinks(selectedMcpCode, initialPolicyLinkIdRef.current);
    initialPolicyLinkIdRef.current = null;
  }, [loadPolicyLinks, selectedMcpCode]);

  useEffect(() => {
    updateSearchParams(selectedMcpCode, selectedPolicyLinkId);
  }, [selectedMcpCode, selectedPolicyLinkId, updateSearchParams]);

  useEffect(() => {
    if (!selectedPolicyLinkId) {
      setPolicyRules(null);
      setPolicyRulesError(null);
      return;
    }
    void loadPolicyRules(selectedPolicyLinkId);
  }, [loadPolicyRules, selectedPolicyLinkId]);

  const handleSelectPolicyLink = (link: PolicyLink) => {
    setSelectedPolicyLinkId(link.id);
  };

  const handleRefreshRules = async () => {
    if (!selectedPolicyLinkId) {
      return;
    }
    setPolicyRefreshLoading(true);
    setPolicyRefreshProposed(null);
    setError(null);
    try {
      const result = await parsePolicyLinkRules(selectedPolicyLinkId, false);
      if ("action_required" in result) {
        setPolicyRefreshProposed(result.proposed_changes);
        setPolicyRefreshDialogOpen(true);
        return;
      }
      if ("status" in result) {
        await loadPolicyRules(selectedPolicyLinkId);
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setPolicyRefreshLoading(false);
    }
  };

  const handleConfirmRefresh = async () => {
    if (!selectedPolicyLinkId) {
      return;
    }
    setPolicyRefreshLoading(true);
    setError(null);
    try {
      const result = await parsePolicyLinkRules(selectedPolicyLinkId, true);
      if ("status" in result) {
        setPolicyRefreshDialogOpen(false);
        setPolicyRefreshProposed(null);
        await loadPolicyRules(selectedPolicyLinkId);
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setPolicyRefreshLoading(false);
    }
  };

  const renderCriteriaNodes = (
    nodes: Array<{ id?: string; text?: string; children?: unknown }>,
    depth: number = 0
  ) => {
    if (!nodes.length) {
      return null;
    }
    return (
      <ul
        className={cn(
          "space-y-2",
          depth > 0 ? "border-l border-slate-200 pl-3 dark:border-slate-700" : ""
        )}
      >
        {nodes.map((node, index) => {
          const children = Array.isArray(node.children) ? node.children : [];
          const key = node.id ?? `${depth}-${index}`;
          return (
            <li key={key} className="space-y-2">
              <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
                {node.text ?? "—"}
              </div>
              {renderCriteriaNodes(
                children as Array<{ id?: string; text?: string; children?: unknown }>,
                depth + 1
              )}
            </li>
          );
        })}
      </ul>
    );
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
              Policy Rules
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {me?.email ?? "Admin"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/app/admin")}>
              <ArrowLeft className="h-4 w-4" />
              Back to admin
            </Button>
          </div>
        </header>

        {error ? <ErrorNotice error={error} /> : null}

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Choose MCP Code</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Select an MCP code to browse related policy rules.
              </p>
            </div>
          </div>
          <div className="mt-4">
            <select
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              value={selectedMcpCode}
              onChange={(event) => {
                setSelectedMcpCode(event.target.value);
              }}
            >
              <option value="">Select MCP code</option>
              {mcpCodes.map((code) => (
                <option key={code.code} value={code.code}>
                  {code.code} {code.description ? `— ${code.description}` : ""}
                </option>
              ))}
            </select>
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Policy Links</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {selectedMcpCode ? `MCP ${selectedMcpCode}` : "Select an MCP code above"}
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleRefreshRules()}
              disabled={!selectedPolicyLinkId || policyRefreshLoading}
            >
              <RefreshCcw className="h-4 w-4" />
              Refresh Rules
            </Button>
          </div>
          <div className="mt-4">
            <DataTable
              rows={policyLinks}
              emptyMessage={
                policyLinksLoading
                  ? "Loading..."
                  : selectedMcpCode
                    ? "No policy links for this MCP code."
                    : "Select an MCP code to see links."
              }
              getRowId={(row) => String(row.id)}
              columns={[
                {
                  key: "company",
                  header: "Company",
                  cell: (row) =>
                    companyById.get(row.insurance_company_id)?.name ??
                    `ID ${row.insurance_company_id}`,
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
                  key: "actions",
                  header: "",
                  cell: (row) => (
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant={row.id === selectedPolicyLinkId ? "secondary" : "outline"}
                        onClick={() => handleSelectPolicyLink(row)}
                        aria-label={`View rules for policy ${row.id}`}
                      >
                        <FileText className="h-4 w-4" />
                        {row.id === selectedPolicyLinkId ? "Selected" : "View rules"}
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

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Parsed Rules</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {selectedPolicyLink
                  ? selectedPolicyLink.policy_url
                  : "Select a policy link to view extracted rules."}
              </p>
            </div>
          </div>

          <div className="mt-4">
            {policyRulesLoading ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-4 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                Loading policy rules...
              </div>
            ) : policyRulesError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
                {policyRulesError}
              </div>
            ) : policyRules ? (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="text-xs uppercase text-slate-400">Title</div>
                    <div className="text-sm font-medium">{policyRules.title ?? "—"}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-slate-400">Next review</div>
                    <div className="text-sm">
                      {formatDateOnly(policyRules.next_review_iso)}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="text-xs uppercase text-slate-400">Medical necessity</div>
                  <div className="max-h-60 overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
                    {policyRules.medical_necessity_clean ??
                      "No medical necessity text available."}
                  </div>
                </div>

                <div>
                  <div className="text-xs uppercase text-slate-400">Criteria</div>
                  {Array.isArray(policyRules.criteria_json) &&
                  policyRules.criteria_json.length > 0 ? (
                    <div className="mt-2">
                      {renderCriteriaNodes(
                        policyRules.criteria_json as Array<{
                          id?: string;
                          text?: string;
                          children?: unknown;
                        }>
                      )}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-500 dark:text-slate-400">
                      No criteria extracted.
                    </div>
                  )}
                </div>

                <div>
                  <div className="text-xs uppercase text-slate-400">Notes</div>
                  {Array.isArray(policyRules.notes_json) &&
                  policyRules.notes_json.length > 0 ? (
                    <ul className="mt-2 space-y-2">
                      {policyRules.notes_json.map(
                        (note: { text?: string }, index: number) => (
                          <li
                            key={`${index}-${note.text ?? "note"}`}
                            className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
                          >
                            {note.text ?? "—"}
                          </li>
                        )
                      )}
                    </ul>
                  ) : (
                    <div className="text-sm text-slate-500 dark:text-slate-400">
                      No notes extracted.
                    </div>
                  )}
                </div>
              </div>
            ) : selectedPolicyLink ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-4 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                No rules parsed yet for this policy link.
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-4 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                Select a policy link to view rules.
              </div>
            )}
          </div>
        </section>

        <Dialog
          open={policyRefreshDialogOpen}
          onOpenChange={(open) => {
            setPolicyRefreshDialogOpen(open);
            if (!open) {
              setPolicyRefreshProposed(null);
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
                  <div className="font-medium">
                    {policyRefreshProposed.title ?? "—"}
                  </div>
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
                onClick={() => void handleConfirmRefresh()}
                disabled={policyRefreshLoading}
              >
                Confirm refresh
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </main>
  );
}
