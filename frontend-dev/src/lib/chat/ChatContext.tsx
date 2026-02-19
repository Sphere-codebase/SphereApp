import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  createSession,
  deleteSession as apiDeleteSession,
  listMessages,
  listSessions,
  sendChatMessage,
  type ChatMessage,
  type ChatResponse,
  type ChatSession,
} from "@/lib/api/chat";
import { getLastRequestId } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthContext";

type ChatRole = "user" | "assistant" | "system";

export interface ChatMessageView {
  id: number | string;
  role: ChatRole;
  content: string;
  created_at?: string;
  isOptimistic?: boolean;
}

export interface ChatContextValue {
  sessions: ChatSession[];
  activeSessionId: number | null;
  messages: ChatMessageView[];
  uiActions: Record<string, unknown>[];
  isLoadingSessions: boolean;
  isLoadingMessages: boolean;
  isSending: boolean;
  actionRequired: boolean;
  proposedChanges: Record<string, unknown> | null;
  error: unknown;
  lastRequestId: string | null;
  llmUnavailable: boolean;
  loadSessions: () => Promise<void>;
  selectSession: (sessionId: number) => void;
  createNewSession: () => Promise<void>;
  deleteSession: (sessionId: number) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  addLocalMessage: (role: ChatRole, content: string) => void;
  clearProposal: () => void;
  clearUiActions: () => void;
  clearError: () => void;
}

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

function normalizeContent(content: string | null | undefined): string {
  return content ?? "";
}

function mapMessages(messages: ChatMessage[]): ChatMessageView[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: normalizeContent(message.content),
    created_at: message.created_at ?? new Date().toISOString(),
  }));
}

function createClientMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  const random = Math.random().toString(16).slice(2, 10);
  return `msg_${Date.now()}_${random}`;
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const { logout } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [uiActions, setUiActions] = useState<Record<string, unknown>[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [actionRequired, setActionRequired] = useState(false);
  const [proposedChanges, setProposedChanges] = useState<Record<string, unknown> | null>(
    null
  );
  const [error, setError] = useState<unknown>(null);
  const [lastRequestId, setLastRequestId] = useState<string | null>(null);
  const [llmUnavailable, setLlmUnavailable] = useState(false);
  const didBootstrapRef = useRef(false);

  const syncRequestId = useCallback(() => {
    const requestId = getLastRequestId();
    if (requestId) {
      setLastRequestId(requestId);
    }
  }, []);

  const handleApiError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          logout();
          return;
        }
        if (err.status === 503) {
          setLlmUnavailable(true);
        }
        setError(err);
        if (err.requestId) {
          setLastRequestId(err.requestId);
        }
      } else {
        setError(err);
      }
      syncRequestId();
    },
    [logout, syncRequestId]
  );

  const createSessionAndSelect = useCallback(async () => {
    setError(null);
    setLlmUnavailable(false);
    const session = await createSession();
    syncRequestId();
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setMessages([]);
    setActionRequired(false);
    setProposedChanges(null);
    setUiActions([]);
    return session;
  }, [syncRequestId]);

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    setError(null);
    setLlmUnavailable(false);
    try {
      const data = await listSessions({ limit: 50, offset: 0 });
      syncRequestId();
      setSessions(data);
      if (data.length === 0) {
        await createSessionAndSelect();
      } else if (!activeSessionId || !data.some((item) => item.id === activeSessionId)) {
        const [first] = data;
        if (first) {
          setActiveSessionId(first.id);
        }
      }
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoadingSessions(false);
    }
  }, [activeSessionId, createSessionAndSelect, handleApiError, syncRequestId]);

  const loadMessages = useCallback(
    async (sessionId: number) => {
      setIsLoadingMessages(true);
      setError(null);
      setLlmUnavailable(false);
      try {
        const data = await listMessages(sessionId);
        syncRequestId();
        setMessages(mapMessages(data));
        setUiActions([]);
      } catch (err) {
        handleApiError(err);
      } finally {
        setIsLoadingMessages(false);
      }
    },
    [handleApiError, syncRequestId]
  );

  const selectSession = useCallback((sessionId: number) => {
    setActiveSessionId(sessionId);
    setActionRequired(false);
    setProposedChanges(null);
    setUiActions([]);
  }, []);

  const createNewSession = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      await createSessionAndSelect();
    } catch (err) {
      handleApiError(err);
    } finally {
      setIsLoadingSessions(false);
    }
  }, [createSessionAndSelect, handleApiError]);

  const deleteSession = useCallback(
    async (sessionId: number) => {
      setIsLoadingSessions(true);
      setError(null);
      setLlmUnavailable(false);
      try {
        await apiDeleteSession(sessionId);
        syncRequestId();
        const remaining = sessions.filter((session) => session.id !== sessionId);
        setSessions(remaining);
        if (activeSessionId === sessionId) {
          if (remaining.length > 0) {
            const [nextSession] = remaining;
            if (nextSession) {
              setActiveSessionId(nextSession.id);
            }
          } else {
            await createSessionAndSelect();
          }
          setMessages([]);
        }
      } catch (err) {
        handleApiError(err);
      } finally {
        setIsLoadingSessions(false);
      }
    },
    [activeSessionId, createSessionAndSelect, handleApiError, sessions, syncRequestId]
  );

  const handleChatResponse = useCallback(
    (response: ChatResponse, clientMessageId: string) => {
      setActionRequired(response.action_required);
      setProposedChanges(response.proposed_changes ?? null);
      setUiActions(response.ui_actions ?? []);
      if (response.assistant_message) {
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-${clientMessageId}`,
            role: "assistant",
            content: response.assistant_message,
          },
        ]);
      }
    },
    []
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) {
        return;
      }
      setError(null);
      setLlmUnavailable(false);
      setActionRequired(false);
      setProposedChanges(null);
      let sessionId = activeSessionId;
      if (!sessionId) {
        try {
          const session = await createSessionAndSelect();
          sessionId = session.id;
        } catch (err) {
          handleApiError(err);
          return;
        }
      }

      const clientMessageId = createClientMessageId();
      const optimisticMessage: ChatMessageView = {
        id: `local-${clientMessageId}`,
        role: "user",
        content: trimmed,
        isOptimistic: true,
      };

      setMessages((prev) => [...prev, optimisticMessage]);
      setIsSending(true);
      try {
      const response = await sendChatMessage({
        session_id: sessionId,
        message: trimmed,
        metadata: { client_message_id: clientMessageId },
      });
        syncRequestId();
        handleChatResponse(response, clientMessageId);
        const refreshed = await listMessages(sessionId);
        syncRequestId();
        setMessages(mapMessages(refreshed));
      } catch (err) {
        handleApiError(err);
      } finally {
        setIsSending(false);
      }
    },
    [activeSessionId, createSessionAndSelect, handleApiError, handleChatResponse, syncRequestId]
  );

  const addLocalMessage = useCallback((role: ChatRole, content: string) => {
    const trimmed = content.trim();
    if (!trimmed) {
      return;
    }
    setMessages((prev) => [
      ...prev,
      {
        id: `local-${createClientMessageId()}`,
        role,
        content: trimmed,
        created_at: new Date().toISOString(),
      },
    ]);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const clearProposal = useCallback(() => {
    setActionRequired(false);
    setProposedChanges(null);
  }, []);

  const clearUiActions = useCallback(() => {
    setUiActions([]);
  }, []);

  useEffect(() => {
    if (didBootstrapRef.current) {
      return;
    }
    didBootstrapRef.current = true;
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    void loadMessages(activeSessionId);
  }, [activeSessionId, loadMessages]);

  const value = useMemo<ChatContextValue>(
    () => ({
      sessions,
      activeSessionId,
      messages,
      uiActions,
      isLoadingSessions,
      isLoadingMessages,
      isSending,
      actionRequired,
      proposedChanges,
      error,
      lastRequestId,
      llmUnavailable,
      loadSessions,
      selectSession,
      createNewSession,
      deleteSession,
      sendMessage,
      addLocalMessage,
      clearProposal,
      clearUiActions,
      clearError,
    }),
    [
      sessions,
      activeSessionId,
      messages,
      uiActions,
      isLoadingSessions,
      isLoadingMessages,
      isSending,
      actionRequired,
      proposedChanges,
      error,
      lastRequestId,
      llmUnavailable,
      loadSessions,
      selectSession,
      createNewSession,
      deleteSession,
      sendMessage,
      addLocalMessage,
      clearProposal,
      clearUiActions,
      clearError,
    ]
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) {
    throw new Error("useChat must be used within ChatProvider");
  }
  return ctx;
}
