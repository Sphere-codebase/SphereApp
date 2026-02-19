import { ChevronDown, Moon, Sun } from "lucide-react";
import { useRef } from "react";
import { Link } from "react-router-dom";

import ChatStatusHud from "@/components/chat/ChatStatusHud";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ThemeMode = "light" | "dark";

type WorkspaceTopBarProps = {
  title: string;
  subtitle?: string;
  theme: ThemeMode;
  isSending: boolean;
  showAdmin: boolean;
  isReadOnly: boolean;
  onOpenUploadPdf: () => void;
  onOpenCreateClaim: () => void;
  onToggleTheme: () => void;
  onLogout: () => void;
};

export default function WorkspaceTopBar({
  title,
  subtitle,
  theme,
  isSending,
  showAdmin,
  isReadOnly,
  onOpenUploadPdf,
  onOpenCreateClaim,
  onToggleTheme,
  onLogout,
}: WorkspaceTopBarProps) {
  const toolsRef = useRef<HTMLDetailsElement | null>(null);

  const closeToolsMenu = () => {
    if (toolsRef.current) {
      toolsRef.current.open = false;
    }
  };

  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
          {subtitle ?? "Workspace"}
        </p>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          {title}
        </h1>
      </div>
      <div className="flex items-center gap-2">
        <ChatStatusHud busy={isSending} />
        <Button asChild type="button" variant="outline">
          <Link to="/app/dashboard">Dashboard</Link>
        </Button>
        {isReadOnly ? (
          <div
            className={cn(
              "rounded-full border border-slate-200 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-500",
              "dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            )}
          >
            Tools
          </div>
        ) : (
          <details ref={toolsRef} className="relative">
            <summary
              className={cn(
                "list-none rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm",
                "cursor-pointer transition hover:border-slate-300 hover:text-slate-900",
                "dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-500"
              )}
            >
              <span className="inline-flex items-center gap-2">
                Tools
                <ChevronDown className="h-4 w-4" />
              </span>
            </summary>
            <div className="absolute right-0 z-20 mt-2 w-44 overflow-hidden rounded-2xl border border-slate-200 bg-white text-sm text-slate-700 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
              <button
                type="button"
                className="w-full px-4 py-2 text-left transition hover:bg-slate-100 dark:hover:bg-slate-800"
                onClick={() => {
                  closeToolsMenu();
                  onOpenUploadPdf();
                }}
              >
                Upload PDF
              </button>
              <button
                type="button"
                className="w-full px-4 py-2 text-left transition hover:bg-slate-100 dark:hover:bg-slate-800"
                onClick={() => {
                  closeToolsMenu();
                  onOpenCreateClaim();
                }}
              >
                Create Claim
              </button>
            </div>
          </details>
        )}
        {showAdmin ? (
          <Button asChild type="button" variant="outline">
            <Link to="/app/admin">Admin</Link>
          </Button>
        ) : null}
        <Button type="button" variant="outline" onClick={onLogout}>
          Logout
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onToggleTheme}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
