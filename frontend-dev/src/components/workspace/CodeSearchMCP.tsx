import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { searchMcpCodes } from "@/api/claims";
import { Button } from "@/components/ui/button";
import type { MCPCodeDTO } from "@/types/claim";
import { ApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type CodeSearchMcpProps = {
  disabled?: boolean;
  existingCodes: string[];
  onAdd: (code: MCPCodeDTO) => void;
};

export default function CodeSearchMCP({
  disabled = false,
  existingCodes,
  onAdd,
}: CodeSearchMcpProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MCPCodeDTO[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);

  const existingSet = useMemo(() => new Set(existingCodes), [existingCodes]);

  useEffect(() => {
    if (disabled || !query.trim()) {
      setResults([]);
      setActiveIndex(-1);
      setError(null);
      setIsSearching(false);
      return;
    }

    let active = true;
    const handle = window.setTimeout(async () => {
      setIsSearching(true);
      setError(null);
      try {
        const data = await searchMcpCodes(query.trim());
        if (active) {
          setResults(data);
          setActiveIndex(data.length ? 0 : -1);
        }
      } catch (err) {
        if (!active) {
          return;
        }
        if (err instanceof ApiError) {
          setError(`Search failed (${err.status}). Try again.`);
        } else {
          setError("Search failed. Try again.");
        }
      } finally {
        if (active) {
          setIsSearching(false);
        }
      }
    }, 300);

    return () => {
      active = false;
      window.clearTimeout(handle);
    };
  }, [disabled, query]);

  const highlight = (text: string) => {
    if (!query.trim()) return text;
    const lower = text.toLowerCase();
    const needle = query.trim().toLowerCase();
    const idx = lower.indexOf(needle);
    if (idx === -1) return text;
    return (
      <>
        {text.slice(0, idx)}
        <mark className="rounded bg-amber-100 px-1 text-amber-900">
          {text.slice(idx, idx + needle.length)}
        </mark>
        {text.slice(idx + needle.length)}
      </>
    );
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (event) => {
    if (!results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const selected = results[activeIndex];
      if (selected && !existingSet.has(selected.code)) {
        onAdd(selected);
      }
    } else if (event.key === "Escape") {
      setResults([]);
      setActiveIndex(-1);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <label className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
        MCP Search
        <div className="mt-2 flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search code or description"
            className="w-full bg-transparent text-sm outline-none"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
          />
        </div>
      </label>

      {isSearching ? (
        <div className="text-xs text-slate-500">Searching...</div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          {error}
        </div>
      ) : null}

      {results.length > 0 ? (
        <div className="flex flex-col gap-2">
          {results.map((code, index) => {
            const exists = existingSet.has(code.code);
            return (
              <div
                key={code.code}
                className={cn(
                  "flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300",
                  exists && "opacity-60",
                  index === activeIndex && "border-emerald-300 ring-1 ring-emerald-200"
                )}
              >
                <div>
                  <div className="text-sm font-semibold text-slate-900 dark:text-white">
                    {highlight(code.code)}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {code.description ? highlight(code.description) : "No description"}
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onAdd(code)}
                  disabled={disabled || exists}
                >
                  {exists ? "Added" : "Add"}
                </Button>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
