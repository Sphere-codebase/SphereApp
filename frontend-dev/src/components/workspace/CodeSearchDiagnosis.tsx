import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { searchDiagnosisCodes } from "@/api/claims";
import { Button } from "@/components/ui/button";
import type { DiagnosisCodeDTO } from "@/types/claim";
import { ApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type CodeSearchDiagnosisProps = {
  disabled?: boolean;
  existingCodes: string[];
  onAdd: (code: DiagnosisCodeDTO) => void;
};

export default function CodeSearchDiagnosis({
  disabled = false,
  existingCodes,
  onAdd,
}: CodeSearchDiagnosisProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DiagnosisCodeDTO[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const existingSet = useMemo(() => new Set(existingCodes), [existingCodes]);

  useEffect(() => {
    if (disabled || !query.trim()) {
      setResults([]);
      setError(null);
      setIsSearching(false);
      return;
    }

    let active = true;
    const handle = window.setTimeout(async () => {
      setIsSearching(true);
      setError(null);
      try {
        const data = await searchDiagnosisCodes(query.trim());
        if (active) {
          setResults(data);
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

  return (
    <div className="flex flex-col gap-3">
      <label className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
        Diagnosis Search
        <div className="mt-2 flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search code or description"
            className="w-full bg-transparent text-sm outline-none"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
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
          {results.map((code) => {
            const exists = existingSet.has(code.code);
            return (
              <div
                key={code.code}
                className={cn(
                  "flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300",
                  exists && "opacity-60"
                )}
              >
                <div>
                  <div className="text-sm font-semibold text-slate-900 dark:text-white">
                    {code.code}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {code.description || "No description"}
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
