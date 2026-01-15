import { CloudUpload, Moon, Plus, Sun, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Conversation } from "@/components/ai/conversation";
import type { MessageProps } from "@/components/ai/message";
import { PromptInput } from "@/components/ai/prompt-input";
import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth/AuthContext";
import { ChatProvider, useChat } from "@/lib/chat/ChatContext";
import { cn } from "@/lib/utils";

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
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

function ChatShell() {
  const {
    sessions,
    activeSessionId,
    messages,
    isLoadingSessions,
    isLoadingMessages,
    actionRequired,
    proposedChanges,
    error,
    lastRequestId,
    llmUnavailable,
    createNewSession,
    selectSession,
    deleteSession,
    sendMessage,
    clearError,
  } = useChat();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);

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

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;

  const handleSend = () => {
    const trimmed = draft.trim();
    if (!trimmed) {
      return;
    }
    setDraft("");
    clearError();
    void sendMessage(trimmed);
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              SphereApp Chat
            </p>
            <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
              {activeSession?.title ?? "Chat sessions"}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => void createNewSession()}
              disabled={isLoadingSessions}
            >
              <Plus className="h-4 w-4" />
              New chat
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
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label="Toggle theme"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[260px_1fr_240px]">
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
                            isActive ? "text-slate-200" : "text-slate-500 dark:text-slate-400"
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
                </CardContent>
              </Card>
            ) : null}

            <div className="flex-1 overflow-auto">
              <Conversation
                messages={conversationMessages}
                emptyState={isLoadingMessages ? "Loading messages..." : "Start a new conversation."}
              />
            </div>

            <PromptInput
              value={draft}
              onChange={setDraft}
              onSubmit={handleSend}
            />

            <details className="text-xs text-slate-500 dark:text-slate-400">
              <summary className="cursor-pointer">Last request ID</summary>
              <div className="mt-2">{lastRequestId ?? "No requests yet."}</div>
            </details>
          </section>

          <aside className="flex flex-col gap-4 rounded-3xl border border-dashed border-slate-200 bg-white p-4 text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
              <CloudUpload className="h-4 w-4" />
              Upload files
            </div>
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400">
              Drop files here to attach them to a session. (UI only)
            </div>
            <Button type="button" variant="outline" disabled>
              Choose files
            </Button>
          </aside>
        </div>
      </div>
    </main>
  );
}

export default function ChatPage() {
  return (
    <ChatProvider>
      <ChatShell />
    </ChatProvider>
  );
}
