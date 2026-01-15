import { Info } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiUrl } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type StatusLevel = "ok" | "err";

type ReadyChecks = {
  db: StatusLevel;
  llm: StatusLevel;
};

type ChatStatusHudProps = {
  busy: boolean;
};

const POLL_INTERVAL_MS = 10000;

// /ready иногда может делать реальный чек LLM — 4s часто мало.
// 15s — безопаснее для dev и не создаёт ложные "вечные жёлтые".
const REQUEST_TIMEOUT_MS = 15000;

function normalizeCheck(value: unknown): StatusLevel {
  return value === "ok" ? "ok" : "err";
}


async function parseJsonStrict(response: Response): Promise<Record<string, unknown>> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error("Non-JSON response");
  }
  const text = await response.text();
  if (!text) {
    throw new Error("Empty JSON response");
  }
  return JSON.parse(text) as Record<string, unknown>;
}

async function fetchWithTimeout(input: RequestInfo, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { cache: "no-store", signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

function statusLabel(status: StatusLevel): string {
  return status === "ok" ? "Active" : "Offline";
}

function lampColor(status: StatusLevel): string {
  return status === "ok"
    ? "bg-emerald-500 shadow-emerald-400/60"
    : "bg-rose-500 shadow-rose-400/60";
}


export default function ChatStatusHud({ busy }: ChatStatusHudProps) {
    const [apiStatus, setApiStatus] = useState<StatusLevel>("err");
    const [readyChecks, setReadyChecks] = useState<ReadyChecks>({
      db: "err",
      llm: "err",
    });

  const [showLegend, setShowLegend] = useState(false);
  const previousBusy = useRef(busy);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetchWithTimeout(apiUrl("/health"), REQUEST_TIMEOUT_MS);
      return response.ok ? ("ok" as const) : ("err" as const);
    } catch {
      // timeout/abort => это не "warn", это "не смогли достучаться"
      return "err" as const;
    }
  }, []);

  const checkReady = useCallback(async () => {
  try {
        const response = await fetchWithTimeout(apiUrl("/ready"), REQUEST_TIMEOUT_MS);

        // читаем JSON ВСЕГДА, даже при 503
        const data = await parseJsonStrict(response);
        const checks = data.checks as Record<string, unknown>;

        if (!checks || checks.db === undefined || checks.llm === undefined) {
          throw new Error("Invalid checks payload");
        }

        return {
          db: normalizeCheck(checks.db),
          llm: normalizeCheck(checks.llm),
        };
      } catch {
        return { db: "err", llm: "err" };
      }
    }, []);



  const poll = useCallback(async () => {
    const [api, ready] = await Promise.all([checkHealth(), checkReady()]);
    setApiStatus(api);
    setReadyChecks(ready);
  }, [checkHealth, checkReady]);

  useEffect(() => {
    void poll();
    const interval = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [poll]);

  useEffect(() => {
    if (previousBusy.current !== busy) {
      previousBusy.current = busy;
      void poll();
    }
  }, [busy, poll]);

  const legend = useMemo(
    () => [
      { label: "Green", value: "Active / ready" },
      { label: "Gray", value: "Disabled (intentional)" },
      { label: "Yellow", value: "Degraded / limited" },
      { label: "Red", value: "Offline" },
    ],
    []
  );

  // Blink only when:
  // - busy
  // - llm is actually active ("ok")
  // Never blink when llm is err/off/warn
  const llmBlink = busy && readyChecks.llm === "ok";

  return (
    <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-white/80 px-3 py-2 text-xs text-slate-600 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-200">
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "h-3 w-3 rounded-full shadow-[0_0_10px] ring-2 ring-white/80 dark:ring-slate-950/70",
            lampColor(apiStatus)
          )}
          title={`API: ${statusLabel(apiStatus)}`}
          aria-label={`API status ${statusLabel(apiStatus)}`}
          data-testid="lamp-api"
        />
        <div
          className={cn(
            "h-3 w-3 rounded-full shadow-[0_0_10px] ring-2 ring-white/80 dark:ring-slate-950/70",
            lampColor(readyChecks.db)
          )}
          title={`DB: ${statusLabel(readyChecks.db)}`}
          aria-label={`DB status ${statusLabel(readyChecks.db)}`}
          data-testid="lamp-db"
        />

        <span data-testid="lamp-llm">
          <div
            className={cn(
              "h-3 w-3 rounded-full shadow-[0_0_10px] ring-2 ring-white/80 dark:ring-slate-950/70",
              lampColor(readyChecks.llm),
              llmBlink && "status-hud-blink"
            )}
            title={`LLM: ${statusLabel(readyChecks.llm)}${llmBlink ? " (busy)" : ""}`}
            aria-label={`LLM status ${statusLabel(readyChecks.llm)}`}
            data-testid="lamp-llm-dot"
          />
        </span>
      </div>

      <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
        Status
      </span>

      <div className="relative">
        <button
          type="button"
          className="flex h-6 w-6 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition hover:text-slate-900 dark:border-slate-800 dark:text-slate-300 dark:hover:text-white"
          aria-label="Status legend"
          onClick={() => setShowLegend((prev) => !prev)}
        >
          <Info className="h-3.5 w-3.5" />
        </button>

        {showLegend ? (
          <div className="absolute right-0 top-8 z-20 w-56 rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-600 shadow-lg dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
              Legend
            </div>
            <div className="flex flex-col gap-1.5">
              {legend.map((item) => (
                <div key={item.label} className="flex items-center justify-between">
                  <span>{item.label}</span>
                  <span className="text-slate-800 dark:text-slate-100">{item.value}</span>
                </div>
              ))}
              <div className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                Lamps: API, DB, LLM.
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
