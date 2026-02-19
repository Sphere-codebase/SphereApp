import { Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  addDiagnosisCode,
  addMcpCode,
  finalizeClaim,
  getClaim,
  generateClaimPdf,
  removeDiagnosisCode,
  removeMcpCode,
} from "@/api/claims";
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
import type { ClaimDTO, DiagnosisCodeDTO, MCPCodeDTO } from "@/types/claim";

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
  } = useChat();
  const { logout, me, hasRole } = useAuth();
  const navigate = useNavigate();
  const { sessionId: routeSessionId } = useParams<{ sessionId?: string }>();
  const [searchParams] = useSearchParams();
  const openCreateClaim = searchParams.get("openCreateClaim") === "1";
  const autoOpenRef = useRef(false);
  const parsedRouteSessionId = routeSessionId ? Number(routeSessionId) : null;
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
  const [isConfirmingProposal, setIsConfirmingProposal] = useState(false);
  const [proposalError, setProposalError] = useState<string | null>(null);

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

  const handleUnauthorized = () => {
    logout();
    navigate("/login");
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

  useEffect(() => {
    setCurrentClaim(null);
    setClaimError(null);
    setIsLoadingClaim(false);
    setDraftPreview({});
    setCreateClaimOpen(false);
    setUploadOpen(false);
    setPdfPreviewUrl(null);
    if (activeSession?.claim_id) {
      void loadClaim(activeSession.claim_id);
    }
  }, [activeSessionId, activeSession?.claim_id]);

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
          showAdmin={hasRole("platform_staff_admin")}
          isReadOnly={isReadOnly}
          claimStatus={currentClaim?.claim_status ?? null}
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
        />

        <div className="grid gap-6 lg:grid-cols-[260px_1fr_260px]">
          <aside className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
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

          <section className="flex min-h-[480px] flex-1 flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
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

            <div className="flex-1 overflow-auto">
              <Conversation
                messages={conversationMessages}
                emptyState={
                  isLoadingMessages ? "Loading messages..." : "Start a new conversation."
                }
              />
            </div>

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
