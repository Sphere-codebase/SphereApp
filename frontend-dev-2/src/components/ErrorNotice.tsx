import { ApiError } from "@/lib/api/errors";

interface ErrorNoticeProps {
  error: unknown;
}

function formatDetails(details: unknown): string | null {
  if (details === null || details === undefined) {
    return null;
  }
  if (typeof details === "string") {
    return details;
  }
  try {
    return JSON.stringify(details, null, 2);
  } catch {
    return null;
  }
}

export default function ErrorNotice({ error }: ErrorNoticeProps) {
  if (!(error instanceof ApiError)) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
        Unexpected error
      </div>
    );
  }

  const code = error.payload?.error.code ?? "UNKNOWN";
  const details = formatDetails(error.payload?.error.details ?? null);

  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
      <div className="font-semibold">Error: {code}</div>
      <div className="mt-1 text-xs text-red-600 dark:text-red-200">{error.message}</div>
      {(details || error.requestId) && (
        <details className="mt-2 text-xs text-red-600 dark:text-red-200">
          <summary className="cursor-pointer">Details</summary>
          {details && <pre className="mt-2 whitespace-pre-wrap">{details}</pre>}
          {error.requestId && (
            <div className="mt-2">Request ID: {error.requestId}</div>
          )}
        </details>
      )}
    </div>
  );
}
