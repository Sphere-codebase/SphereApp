import { Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  addDiagnosisCode,
  addMcpCode,
  finalizeClaim,
  getClaim,
  getClaimFinancialSummary,
  getClaimRequirements,
  generateClaimPdf,
  removeDiagnosisCode,
  removeMcpCode,
  refreshClaimFinancialSummary,
} from "@/api/claims";
import { getPatient } from "@/api/patients";
import { Conversation } from "@/components/ai/conversation";
import type { MessageProps } from "@/components/ai/message";
import { PromptInput } from "@/components/ai/prompt-input";
import ErrorNotice from "@/components/ErrorNotice";
import ClaimDraftPanel from "@/components/workspace/ClaimDraftPanel";
import WorkspaceTopBar from "@/components/workspace/WorkspaceTopBar";
import CreateClaimTool from "@/components/workspace/tools/CreateClaimTool";
import UploadPdfTool from "@/components/workspace/tools/UploadPdfTool";
import type { ClaimDraftPreview } from "@/components/workspace/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth/AuthContext";
import { confirmChatAction } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/errors";
import { ChatProvider, useChat } from "@/lib/chat/ChatContext";
import { cn } from "@/lib/utils";
import type {
  ClaimDTO,
  ClaimFinancialSummaryDTO,
  ClaimRequirementsDTO,
  DiagnosisCodeDTO,
  MCPCodeDTO,
} from "@/types/claim";
import type { PatientDetailDTO } from "@/types/patients";

type ThemeMode = "light" | "dark";

const THEME_STORAGE_KEY = "sphereapp-theme";

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "light";
  }
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  const prefersDark = window.matchMedia
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : false;
  return prefersDark ? "dark" : "light";
}

function formatTime(value?: string | null): string | undefined {
  if (!value) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function WorkspaceShell() {
  const {
    sessions,
    activeSessionId,
    messages,
    isLoadingSessions,
    isLoadingMessages,
    isSending,
    actionRequired,
    proposedChanges,
    uiActions,
    error,
    lastRequestId,
    llmUnavailable,
    createNewSession,
    loadSessions,
    selectSession,
    deleteSession,
    sendMessage,
    clearError,
    addLocalMessage,
    clearProposal,
    clearUiActions,
  } = useChat();
  const { logout, me, hasRole } = useAuth();
  const navigate = useNavigate();
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>();
  const [searchParams] = useSearchParams();
  const openCreateClaim = searchParams.get("openCreateClaim") === "1";
  const patientIdParam = searchParams.get("patientId");
  const claimIdParam = searchParams.get("claimId");
  const autoOpenRef = useRef(false);
  const parsedRouteSessionId = routeSessionId ? Number(routeSessionId) : null;
  const parsedPatientId = patientIdParam ? Number(patientIdParam) : null;
  const parsedClaimId = claimIdParam ? Number(claimIdParam) : null;
  const [draft, setDraft] = useState("");
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [createClaimOpen, setCreateClaimOpen] = useState(false);
  const [currentClaim, setCurrentClaim] = useState<ClaimDTO | null>(null);
  const [isLoadingClaim, setIsLoadingClaim] = useState(false);
  const [claimError, setClaimError] = useState<string | null>(null);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [draftPreview, setDraftPreview] = useState<Partial<ClaimDraftPreview>>({});
  const [selectedPatient, setSelectedPatient] = useState<PatientDetailDTO | null>(null);
  const [patientError, setPatientError] = useState<string | null>(null);
  const [isLoadingPatient, setIsLoadingPatient] = useState(false);
  const [isConfirmingProposal, setIsConfirmingProposal] = useState(false);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [financialSummary, setFinancialSummary] = useState<ClaimFinancialSummaryDTO | null>(
    null
  );
  const [isLoadingFinancial, setIsLoadingFinancial] = useState(false);
  const [financialError, setFinancialError] = useState<string | null>(null);
  const financialKeyRef = useRef<string | null>(null);
  const [requirements, setRequirements] = useState<ClaimRequirementsDTO | null>(null);
  const [isCheckingRequirements, setIsCheckingRequirements] = useState(false);
  const [requirementsError, setRequirementsError] = useState<string | null>(null);
  const [missingFieldAnswers, setMissingFieldAnswers] = useState<Record<string, string>>(
    {}
  );
  const [formResponses, setFormResponses] = useState<Record<string, string>>({});

  const handleUnauthorized = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const conversationMessages = useMemo<MessageProps[]>(
    () =>
      messages.map((message) => {
        const timestamp = formatTime(message.created_at);
        return timestamp
          ? { role: message.role, content: message.content, timestamp }
          : { role: message.role, content: message.content };
      }),
    [messages]
  );

  const activeSession =
    sessions.find((session) => session.id === activeSessionId) ?? null;
  const isReadOnly = currentClaim?.claim_status === "final";

  useEffect(() => {
    if (isReadOnly) {
      setUploadOpen(false);
      setCreateClaimOpen(false);
    }
  }, [isReadOnly]);

  useEffect(() => {
    if (!actionRequired) {
      setProposalError(null);
      return;
    }
    setProposalError(null);
  }, [actionRequired, proposedChanges]);

  useEffect(() => {
    if (!parsedRouteSessionId || !Number.isFinite(parsedRouteSessionId)) {
      return;
    }
    if (activeSessionId === parsedRouteSessionId) {
      return;
    }
    const exists = sessions.some((session) => session.id === parsedRouteSessionId);
    if (exists) {
      selectSession(parsedRouteSessionId);
    }
  }, [activeSessionId, parsedRouteSessionId, selectSession, sessions]);

  useEffect(() => {
    if (!openCreateClaim || autoOpenRef.current) {
      return;
    }
    if (isReadOnly) {
      return;
    }
    if (!activeSessionId) {
      return;
    }
    if (parsedRouteSessionId && activeSessionId !== parsedRouteSessionId) {
      return;
    }
    autoOpenRef.current = true;
    setCreateClaimOpen(true);
  }, [activeSessionId, isReadOnly, openCreateClaim, parsedRouteSessionId]);

  useEffect(() => {
    if (!parsedPatientId || !Number.isFinite(parsedPatientId)) {
      setSelectedPatient(null);
      setPatientError(null);
      setIsLoadingPatient(false);
      return;
    }
    setIsLoadingPatient(true);
    setPatientError(null);
    getPatient(parsedPatientId)
      .then((patient) => {
        setSelectedPatient(patient);
        setDraftPreview((prev) => ({
          ...prev,
          patient: {
            first_name: patient.first_name ?? "",
            last_name: patient.last_name ?? "",
            date_of_birth: patient.date_of_birth ?? "",
          },
        }));
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          handleUnauthorized();
          return;
        }
        setSelectedPatient(null);
        setPatientError("Unable to load selected patient.");
      })
      .finally(() => {
        setIsLoadingPatient(false);
      });
  }, [parsedPatientId, handleUnauthorized]);

  useEffect(() => {
    setRequirements(null);
    setRequirementsError(null);
    setMissingFieldAnswers({});
    setFormResponses({});
  }, [currentClaim?.id]);

  const formAction = useMemo(() => {
    if (!uiActions?.length) {
      return null;
    }
    const action = uiActions.find((item) => item.type === "form");
    if (!action || !Array.isArray(action.fields)) {
      return null;
    }
    return action as { type: string; fields: Array<Record<string, unknown>> };
  }, [uiActions]);

  const handleSend = () => {
    if (isReadOnly) {
      return;
    }
    const trimmed = draft.trim();
    if (!trimmed) {
      return;
    }
    setDraft("");
    clearError();
    void sendMessage(trimmed);
  };

  const loadClaim = async (claimId: number) => {
    setIsLoadingClaim(true);
    setClaimError(null);
    try {
      const claim = await getClaim(claimId);
      setCurrentClaim(claim);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setClaimError("Claim not found.");
      } else {
        setClaimError("Unable to load claim.");
      }
      setCurrentClaim(null);
    } finally {
      setIsLoadingClaim(false);
    }
  };

  const financialKey = useMemo(() => {
    if (!currentClaim) {
      return null;
    }
    const mcpKey = currentClaim.mcp_codes.map((code) => code.code).sort().join("|");
    const diagnosisKey = currentClaim.diagnosis_codes
      .map((code) => code.code)
      .sort()
      .join("|");
    return `${currentClaim.id}:${currentClaim.insurance_company_id}:${mcpKey}:${diagnosisKey}`;
  }, [currentClaim]);

  const fetchFinancialSummary = useCallback(
    async (claim: ClaimDTO, options?: { force?: boolean; refresh?: boolean }) => {
      if (!options?.force && financialKeyRef.current === financialKey) {
        return;
      }
      setIsLoadingFinancial(true);
      setFinancialError(null);
      try {
        const summary = options?.refresh
          ? await refreshClaimFinancialSummary(claim.id)
          : await getClaimFinancialSummary(claim.id);
        setFinancialSummary(summary);
        financialKeyRef.current = financialKey;
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          handleUnauthorized();
          return;
        }
        setFinancialError("Unable to load financial insights.");
      } finally {
        setIsLoadingFinancial(false);
      }
    },
    [financialKey, getClaimFinancialSummary, handleUnauthorized, refreshClaimFinancialSummary]
  );

  useEffect(() => {
    if (!parsedClaimId || !Number.isFinite(parsedClaimId)) {
      return;
    }
    const match = sessions.find((session) => session.claim_id === parsedClaimId);
    if (match && activeSessionId !== match.id) {
      selectSession(match.id);
    }
  }, [activeSessionId, parsedClaimId, selectSession, sessions]);

  useEffect(() => {
    setClaimError(null);
    setIsLoadingClaim(false);
    setPdfPreviewUrl(null);
    if (activeSession?.claim_id) {
      setCurrentClaim(null);
      setDraftPreview({});
      setCreateClaimOpen(false);
      setUploadOpen(false);
      void loadClaim(activeSession.claim_id);
      return;
    }
    if (parsedClaimId && Number.isFinite(parsedClaimId)) {
      setCurrentClaim(null);
      setDraftPreview({});
      setCreateClaimOpen(false);
      setUploadOpen(false);
      void loadClaim(parsedClaimId);
      return;
    }
    setCurrentClaim(null);
    setDraftPreview({});
    setCreateClaimOpen(false);
    setUploadOpen(false);
  }, [activeSessionId, activeSession?.claim_id, parsedClaimId]);

  useEffect(() => {
    if (!currentClaim) {
      setFinancialSummary(null);
      setFinancialError(null);
      setIsLoadingFinancial(false);
      financialKeyRef.current = null;
      return;
    }
    if (financialSummary && financialSummary.claim_id !== currentClaim.id) {
      setFinancialSummary(null);
    }
    void fetchFinancialSummary(currentClaim);
  }, [currentClaim, fetchFinancialSummary, financialSummary]);

  const handleClaimCreated = (claim: ClaimDTO) => {
    setCurrentClaim(claim);
    setClaimError(null);
    setDraftPreview({
      patient: claim.patient,
      insurance_company_id:
        claim.insurance_company_id !== null && claim.insurance_company_id !== undefined
          ? String(claim.insurance_company_id)
          : "",
      service_date: claim.service_date ?? "",
    });
    void loadSessions();
  };

  const handleFinalizeClaim = async () => {
    if (!currentClaim || currentClaim.claim_status === "final") {
      return;
    }
    setIsFinalizing(true);
    setClaimError(null);
    try {
      const updated = await finalizeClaim(currentClaim.id);
      setCurrentClaim(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setClaimError("Unable to finalize claim.");
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleGeneratePdf = async () => {
    if (!currentClaim) {
      return;
    }
    setIsGeneratingPdf(true);
    setClaimError(null);
    try {
      const result = await generateClaimPdf(currentClaim.id);
      setPdfPreviewUrl(result.pdf_url);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setClaimError("Unable to generate PDF.");
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const handleCheckRequirements = async () => {
    if (!currentClaim) {
      return;
    }
    setIsCheckingRequirements(true);
    setRequirementsError(null);
    try {
      const response = await getClaimRequirements(currentClaim.id);
      setRequirements(response);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setRequirementsError("Unable to check claim requirements.");
    } finally {
      setIsCheckingRequirements(false);
    }
  };

  const handleRefreshFinancial = async () => {
    if (!currentClaim) {
      return;
    }
    await fetchFinancialSummary(currentClaim, { force: true, refresh: true });
  };

  const handleProposalDecision = async (decision: "confirm" | "reject") => {
    if (!activeSessionId) {
      setProposalError("No active session available.");
      return;
    }
    if (!proposedChanges || typeof proposedChanges !== "object") {
      setProposalError("Missing proposal details.");
      return;
    }
    const proposal = proposedChanges as Record<string, unknown>;
    const tool = typeof proposal.tool === "string" ? proposal.tool : null;
    if (!tool) {
      setProposalError("Missing proposal tool information.");
      return;
    }
    const argumentsPayload =
      proposal.arguments && typeof proposal.arguments === "object"
        ? (proposal.arguments as Record<string, unknown>)
        : {};
    const proposalId = typeof proposal.proposal_id === "string" ? proposal.proposal_id : null;
    const payload =
      proposal.proposed_changes && typeof proposal.proposed_changes === "object"
        ? (proposal.proposed_changes as Record<string, unknown>)
        : null;

    setIsConfirmingProposal(true);
    setProposalError(null);
    try {
      const result = await confirmChatAction({
        session_id: activeSessionId,
        proposal_id: proposalId,
        decision,
        tool,
        arguments: argumentsPayload,
        payload,
      });
      clearProposal();
      addLocalMessage(
        "system",
        decision === "confirm" ? "AI proposal confirmed." : "AI proposal rejected."
      );

      if (decision === "confirm") {
        let claimId: number | null = null;
        const resultClaimId = result.result ? result.result["claim_id"] : undefined;
        if (typeof resultClaimId === "number") {
          claimId = resultClaimId;
        } else if (tool === "update_claim_fields") {
          const argumentId = argumentsPayload["claim_id"];
          if (typeof argumentId === "number") {
            claimId = argumentId;
          } else if (currentClaim) {
            claimId = currentClaim.id;
          }
        }
        if (claimId) {
          await loadClaim(claimId);
        }
        await loadSessions();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setProposalError("Unable to apply proposal.");
    } finally {
      setIsConfirmingProposal(false);
    }
  };

  const handleAddMcpCode = async (code: MCPCodeDTO) => {
    if (!currentClaim || currentClaim.claim_status === "final") {
      return;
    }
    if (currentClaim.mcp_codes.some((item) => item.code === code.code)) {
      return;
    }
    const previous = currentClaim;
    setCurrentClaim({
      ...previous,
      mcp_codes: [...previous.mcp_codes, code],
    });
    try {
      await addMcpCode(previous.id, code.code);
      setClaimError(null);
    } catch (err) {
      setCurrentClaim(previous);
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setClaimError("Unable to add procedure code.");
    }
  };

  const handleRemoveMcpCode = async (code: MCPCodeDTO) => {
    if (!currentClaim || currentClaim.claim_status === "final") {
      return;
    }
    if (!currentClaim.mcp_codes.some((item) => item.code === code.code)) {
      return;
    }
    const previous = currentClaim;
    setCurrentClaim({
      ...previous,
      mcp_codes: previous.mcp_codes.filter((item) => item.code !== code.code),
    });
    try {
      await removeMcpCode(previous.id, code.code);
      setClaimError(null);
    } catch (err) {
      setCurrentClaim(previous);
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setClaimError("Unable to remove procedure code.");
    }
  };

  const handleAddDiagnosisCode = async (code: DiagnosisCodeDTO) => {
    if (!currentClaim || currentClaim.claim_status === "final") {
      return;
    }
    if (currentClaim.diagnosis_codes.some((item) => item.code === code.code)) {
      return;
    }
    const previous = currentClaim;
    setCurrentClaim({
      ...previous,
      diagnosis_codes: [...previous.diagnosis_codes, code],
    });
    try {
      await addDiagnosisCode(previous.id, code.code);
      setClaimError(null);
    } catch (err) {
      setCurrentClaim(previous);
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setClaimError("Unable to add diagnosis code.");
    }
  };

  const handleRemoveDiagnosisCode = async (code: DiagnosisCodeDTO) => {
    if (!currentClaim || currentClaim.claim_status === "final") {
      return;
    }
    if (!currentClaim.diagnosis_codes.some((item) => item.code === code.code)) {
      return;
    }
    const previous = currentClaim;
    setCurrentClaim({
      ...previous,
      diagnosis_codes: previous.diagnosis_codes.filter((item) => item.code !== code.code),
    });
    try {
      await removeDiagnosisCode(previous.id, code.code);
      setClaimError(null);
    } catch (err) {
      setCurrentClaim(previous);
      if (err instanceof ApiError && err.status === 401) {
        handleUnauthorized();
        return;
      }
      setClaimError("Unable to remove diagnosis code.");
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <WorkspaceTopBar
          title={activeSession?.title ?? "Chat sessions"}
          subtitle={me?.clinic_name ?? "SphereApp Chat"}
          theme={theme}
          isSending={isSending}
          showAdmin={hasRole(["platform_staff_admin", "clinic_admin", "chief_doctor"])}
          claimStatus={currentClaim?.claim_status ?? null}
          onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          onLogout={handleUnauthorized}
        />

        <UploadPdfTool
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          sessionId={activeSessionId}
          onUnauthorized={handleUnauthorized}
          onSystemMessage={(message) => addLocalMessage("system", message)}
        />
        <CreateClaimTool
          open={createClaimOpen}
          onOpenChange={setCreateClaimOpen}
          draftPreview={draftPreview}
          onDraftChange={setDraftPreview}
          onUnauthorized={handleUnauthorized}
          onClaimCreated={handleClaimCreated}
          sessionId={activeSessionId}
          selectedPatient={selectedPatient}
          patientError={patientError}
          isLoadingPatient={isLoadingPatient}
        />

        <div className="grid gap-6 lg:grid-cols-[260px_1fr_260px]">
          <aside className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <Link
              to="/app/dashboard"
              className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50 border border-slate-200 bg-white text-slate-900 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 h-11 px-5"
            >
              Dashboard
            </Link>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Sessions
              </h2>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => void createNewSession()}
                disabled={isLoadingSessions}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
            {isLoadingSessions && sessions.length === 0 ? (
              <div className="text-sm text-slate-500">Loading sessions...</div>
            ) : (
              <div className="flex flex-col gap-2">
                {sessions.map((session, index) => {
                  const isActive = session.id === activeSessionId;
                  return (
                    <div
                      key={session.id}
                      className={cn(
                        "flex items-center justify-between gap-2 rounded-2xl border px-3 py-2 text-left text-sm",
                        isActive
                          ? "border-slate-900 bg-slate-900 text-white"
                          : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-700"
                      )}
                    >
                      <button
                        type="button"
                        className="flex flex-1 flex-col gap-1 text-left"
                        onClick={() => selectSession(session.id)}
                        disabled={isLoadingMessages}
                      >
                        <span className="font-medium">
                          {session.title ?? `Session ${sessions.length - index}`}
                        </span>
                        <span
                          className={cn(
                            "text-xs",
                            isActive
                              ? "text-slate-200"
                              : "text-slate-500 dark:text-slate-400"
                          )}
                        >
                          {formatTime(session.created_at) ?? "—"}
                        </span>
                      </button>
                      <Button
                        type="button"
                        size="sm"
                        variant={isActive ? "secondary" : "outline"}
                        aria-label="Delete session"
                        onClick={() => void deleteSession(session.id)}
                        disabled={isLoadingSessions}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </aside>

          <section className="flex min-h-[480px] min-h-0 flex-1 flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            {llmUnavailable ? (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
                LLM unavailable, retry later.
              </div>
            ) : null}

            {error ? <ErrorNotice error={error} /> : null}

            {actionRequired ? (
              <Card className="border-amber-200 bg-amber-50">
                <CardHeader>
                  <CardTitle>Action required</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-amber-900">
                    Review the proposed changes below before continuing.
                  </p>
                  <pre className="mt-3 max-h-40 overflow-auto rounded-2xl bg-white p-3 text-xs text-slate-700">
                    {JSON.stringify(proposedChanges ?? {}, null, 2)}
                  </pre>
                  {proposalError ? (
                    <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                      {proposalError}
                    </div>
                  ) : null}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => void handleProposalDecision("confirm")}
                      disabled={isReadOnly || isConfirmingProposal}
                    >
                      {isConfirmingProposal ? "Confirming..." : "Confirm"}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void handleProposalDecision("reject")}
                      disabled={isReadOnly || isConfirmingProposal}
                    >
                      Reject
                    </Button>
                    {isReadOnly ? (
                      <span className="text-xs text-amber-700">
                        Claim is finalized. Proposals are locked.
                      </span>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            ) : null}

            <div className="min-h-0 flex-1">
              <Conversation
                messages={conversationMessages}
                emptyState={
                  isLoadingMessages ? "Loading messages..." : "Start a new conversation."
                }
              />
            </div>

            {formAction ? (
              <Card className="border-indigo-200 bg-indigo-50">
                <CardHeader>
                  <CardTitle>Additional Info Requested</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-indigo-900">
                  <div className="text-sm">
                    The assistant needs a few more details to continue.
                  </div>
                  <div className="space-y-2">
                    {formAction.fields.map((field, index) => {
                      const key =
                        (field.key as string) ||
                        (field.name as string) ||
                        `field_${index}`;
                      const label =
                        (field.label as string) ||
                        (field.question as string) ||
                        key;
                      return (
                        <label key={key} className="flex flex-col gap-1 text-xs">
                          <span className="font-semibold">{label}</span>
                          <input
                            type="text"
                            value={formResponses[key] ?? ""}
                            onChange={(event) =>
                              setFormResponses((prev) => ({
                                ...prev,
                                [key]: event.target.value,
                              }))
                            }
                            className="rounded-xl border border-indigo-200 bg-white px-3 py-2 text-sm text-slate-900"
                            disabled={isReadOnly}
                          />
                        </label>
                      );
                    })}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        const payload = { fields: formAction.fields, answers: formResponses };
                        void sendMessage(`Form responses: ${JSON.stringify(payload)}`);
                        setFormResponses({});
                        clearUiActions();
                      }}
                      disabled={isReadOnly}
                    >
                      Send to Assistant
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => clearUiActions()}
                    >
                      Dismiss
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : null}

            {requirements?.missing?.length ? (
              <Card className="border-amber-200 bg-amber-50">
                <CardHeader>
                  <CardTitle>Missing Claim Fields</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-amber-900">
                  <div className="text-sm">
                    The following fields are still missing. You can answer here to
                    send them back to the assistant.
                  </div>
                  <div className="space-y-2">
                    {requirements.missing.map((item) => (
                      <label key={item.key} className="flex flex-col gap-1 text-xs">
                        <span className="font-semibold">{item.question}</span>
                        <input
                          type="text"
                          value={missingFieldAnswers[item.key] ?? ""}
                          onChange={(event) =>
                            setMissingFieldAnswers((prev) => ({
                              ...prev,
                              [item.key]: event.target.value,
                            }))
                          }
                          className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm text-slate-900"
                          disabled={isReadOnly}
                        />
                      </label>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        const payload = {
                          missing_fields: requirements.missing.map((item) => item.key),
                          answers: missingFieldAnswers,
                        };
                        void sendMessage(
                          `Missing field answers: ${JSON.stringify(payload)}`
                        );
                        setMissingFieldAnswers({});
                      }}
                      disabled={isReadOnly}
                    >
                      Send to Assistant
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setRequirements(null)}
                    >
                      Dismiss
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : null}

            <PromptInput
              value={draft}
              onChange={setDraft}
              onSubmit={handleSend}
              disabled={isReadOnly}
              placeholder={
                isReadOnly
                  ? "This claim is finalized. Start a new claim to continue."
                  : "Send a message..."
              }
            />
            {isReadOnly ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                This claim is finalized. Start a new claim to continue.
              </div>
            ) : null}

            <details className="text-xs text-slate-500 dark:text-slate-400">
              <summary className="cursor-pointer">Last request ID</summary>
              <div className="mt-2">{lastRequestId ?? "No requests yet."}</div>
            </details>
          </section>

          <ClaimDraftPanel
            currentClaim={currentClaim}
            draftPreview={draftPreview}
            isLoading={isLoadingClaim}
            claimError={claimError}
            showAdmin={hasRole(["platform_staff_admin", "clinic_admin", "chief_doctor"])}
            onOpenUploadPdf={() => {
              if (!isReadOnly) {
                setUploadOpen(true);
              }
            }}
            onOpenCreateClaim={() => {
              if (!isReadOnly) {
                setCreateClaimOpen(true);
              }
            }}
            onAddMcpCode={handleAddMcpCode}
            onRemoveMcpCode={handleRemoveMcpCode}
            onAddDiagnosisCode={handleAddDiagnosisCode}
            onRemoveDiagnosisCode={handleRemoveDiagnosisCode}
            onFinalizeClaim={handleFinalizeClaim}
            isFinalizing={isFinalizing}
            onGeneratePdf={handleGeneratePdf}
            isGeneratingPdf={isGeneratingPdf}
            pdfPreviewUrl={pdfPreviewUrl}
            onClosePdfPreview={() => setPdfPreviewUrl(null)}
            financialSummary={financialSummary}
            isLoadingFinancial={isLoadingFinancial}
            financialError={financialError}
            onRefreshFinancial={handleRefreshFinancial}
            requirements={requirements}
            isCheckingRequirements={isCheckingRequirements}
            requirementsError={requirementsError}
            onCheckRequirements={handleCheckRequirements}
          />
        </div>
      </div>
    </main>
  );
}

export default function WorkspacePage() {
  return (
    <ChatProvider>
      <WorkspaceShell />
    </ChatProvider>
  );
}
