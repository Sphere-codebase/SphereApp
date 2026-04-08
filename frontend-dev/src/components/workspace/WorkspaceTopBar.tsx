import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import ChatStatusHud from "@/components/chat/ChatStatusHud";
import { Button } from "@/components/ui/button";
import { getInitialTheme, THEME_STORAGE_KEY } from "@/lib/utils";

type ThemeMode = "light" | "dark";

type WorkspaceTopBarProps = {
  title: string;
  subtitle?: string;
  isSending: boolean;
  showAdmin: boolean;
  claimStatus?: "draft" | "final" | null;
  onLogout: () => void;
};

export default function WorkspaceTopBar({
  title,
  subtitle,
  isSending,
  showAdmin,
  claimStatus = null,
  onLogout,
}: WorkspaceTopBarProps) {
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

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
        <NavLink
          to="/app/chat"
          className={({ isActive }) =>
            `inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-colors h-11 px-5 border ${
              isActive
                ? "bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900" // Активный стиль
                : "bg-white text-slate-900 border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100" // Обычный стиль
            }`
          }
        >
          Chat
        </NavLink>
        <NavLink
          className={({ isActive }) =>
            `inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-colors h-11 px-5 border ${
              isActive
                ? "bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900" // Активный стиль
                : "bg-white text-slate-900 border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100" // Обычный стиль
            }`
          }
          to="/app/dashboard"
        >
          Dashboard
        </NavLink>
        {showAdmin ? (
          <NavLink
            className={({ isActive }) =>
              `inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-colors h-11 px-5 border ${
                isActive
                  ? "bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900" // Активный стиль
                  : "bg-white text-slate-900 border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100" // Обычный стиль
              }`
            }
            to="/app/admin"
          >
            Admin
          </NavLink>
        ) : null}
        <Button type="button" variant="outline" onClick={onLogout}>
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
  );
}
