import { Moon, Sun } from "lucide-react";
import { Link } from "react-router-dom";
import ChatStatusHud from "@/components/chat/ChatStatusHud";
import { Button } from "@/components/ui/button";

type ThemeMode = "light" | "dark";

type WorkspaceTopBarProps = {
  title: string;
  subtitle?: string;
  theme: ThemeMode;
  isSending: boolean;
  showAdmin: boolean;
  claimStatus?: "draft" | "final" | null;
  onToggleTheme: () => void;
  onLogout: () => void;
};

export default function WorkspaceTopBar({
  title,
  subtitle,
  theme,
  isSending,
  showAdmin,
  claimStatus = null,
  onToggleTheme,
  onLogout,
}: WorkspaceTopBarProps) {
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
        {claimStatus ? (
          <span
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold",
              claimStatus === "final"
                ? "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
                : "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200"
            )}
          >
            {claimStatus === "final" ? "Finalized" : "Draft"}
          </span>
        ) : null}
        {showAdmin ? (
          <Link
            className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50 border border-slate-200 bg-white text-slate-900 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 h-11 px-5"
            type="button"
            to="/app/admin"
          >
            Admin
          </Link>
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
