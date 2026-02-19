import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}

function highlight(text: string, query: string): JSX.Element | string {
  if (!query.trim()) {
    return text;
  }
  const lower = text.toLowerCase();
  const needle = query.toLowerCase();
  const index = lower.indexOf(needle);
  if (index === -1) {
    return text;
  }
  const before = text.slice(0, index);
  const match = text.slice(index, index + query.length);
  const after = text.slice(index + query.length);
  return (
    <>
      {before}
      <mark className="rounded bg-amber-100 px-1 text-amber-900">{match}</mark>
      {after}
    </>
  );
}

type JsonNodeProps = {
  label?: string;
  value: unknown;
  depth?: number;
  search: string;
};

function JsonNode({ label, value, depth = 0, search }: JsonNodeProps) {
  const [open, setOpen] = useState(depth < 1);
  const indent = depth * 16;

  if (isArray(value)) {
    return (
      <div style={{ paddingLeft: indent }}>
        <button
          type="button"
          className="flex items-center gap-2 text-left text-xs font-semibold text-slate-600"
          onClick={() => setOpen((prev) => !prev)}
        >
          <span>{open ? "▾" : "▸"}</span>
          <span>
            {label ? (
              <>
                {highlight(label, search)}:{" "}
              </>
            ) : null}
            Array({value.length})
          </span>
        </button>
        {open ? (
          <div className="mt-1 space-y-1">
            {value.map((entry, index) => (
              <JsonNode
                key={`${label ?? "array"}-${index}`}
                label={`[${index}]`}
                value={entry}
                depth={depth + 1}
                search={search}
              />
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  if (isObject(value)) {
    const entries = Object.entries(value);
    return (
      <div style={{ paddingLeft: indent }}>
        <button
          type="button"
          className="flex items-center gap-2 text-left text-xs font-semibold text-slate-600"
          onClick={() => setOpen((prev) => !prev)}
        >
          <span>{open ? "▾" : "▸"}</span>
          <span>
            {label ? (
              <>
                {highlight(label, search)}:{" "}
              </>
            ) : null}
            Object({entries.length})
          </span>
        </button>
        {open ? (
          <div className="mt-1 space-y-1">
            {entries.map(([key, entry]) => (
              <JsonNode key={key} label={key} value={entry} depth={depth + 1} search={search} />
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  const text = value === null || value === undefined ? "null" : String(value);
  return (
    <div style={{ paddingLeft: indent }} className="text-xs text-slate-600">
      <span className="font-semibold text-slate-700">
        {label ? (
          <>
            {highlight(label, search)}:{" "}
          </>
        ) : null}
      </span>
      <span className="text-slate-500">{highlight(text, search)}</span>
    </div>
  );
}

type JsonViewerProps = {
  data: unknown;
  emptyLabel?: string;
};

export default function JsonViewer({ data, emptyLabel = "No data." }: JsonViewerProps) {
  const [view, setView] = useState<"tree" | "raw">("tree");
  const [search, setSearch] = useState("");
  const [copied, setCopied] = useState(false);

  const rawText = useMemo(() => {
    if (view !== "raw") {
      return "";
    }
    try {
      return JSON.stringify(data ?? {}, null, 2);
    } catch {
      return "";
    }
  }, [data, view]);

  const handleCopy = async () => {
    try {
      const text = JSON.stringify(data ?? {}, null, 2);
      await navigator.clipboard?.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const isEmpty = !data || (isObject(data) && Object.keys(data).length === 0);

  if (isEmpty) {
    return <div className="text-xs text-slate-500">{emptyLabel}</div>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={view === "tree" ? "secondary" : "outline"}
            onClick={() => setView("tree")}
          >
            Tree
          </Button>
          <Button
            type="button"
            size="sm"
            variant={view === "raw" ? "secondary" : "outline"}
            onClick={() => setView("raw")}
          >
            Raw
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search JSON"
            className="rounded-xl border border-slate-200 bg-white px-3 py-1 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Button type="button" size="sm" variant="outline" onClick={handleCopy}>
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>
      {view === "tree" ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
          <JsonNode value={data} search={search} />
        </div>
      ) : (
        <pre
          className={cn(
            "max-h-96 overflow-auto rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-600",
            "dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
          )}
        >
          {rawText}
        </pre>
      )}
    </div>
  );
}
