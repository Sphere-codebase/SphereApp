import { CloudUpload } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ingestPdf, type ClaimPdfIngestResponse } from "@/api/claims";
import ErrorNotice from "@/components/ErrorNotice";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type UploadStatus = "idle" | "uploading" | "success" | "error";

type UploadPdfToolProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sessionId?: number | null;
  onUnauthorized: () => void;
  onSystemMessage: (message: string) => void;
};

export default function UploadPdfTool({
  open,
  onOpenChange,
  sessionId,
  onUnauthorized,
  onSystemMessage,
}: UploadPdfToolProps) {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [response, setResponse] = useState<ClaimPdfIngestResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) {
      setStatus("idle");
      setFile(null);
      setResponse(null);
      setError(null);
      setIsDragging(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }, [open]);

  const handleFile = (nextFile: File | undefined | null) => {
    if (!nextFile) {
      return;
    }
    const isPdf =
      nextFile.type === "application/pdf" ||
      nextFile.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setError(new Error("Please select a PDF file."));
      return;
    }
    setFile(nextFile);
    setStatus("idle");
    setError(null);
    setResponse(null);
  };

  const handleUpload = async () => {
    if (!file) {
      return;
    }
    setStatus("uploading");
    setError(null);
    try {
      const data = await ingestPdf(file, sessionId);
      setResponse(data);
      setStatus("success");
      onSystemMessage(`PDF uploaded and ingested: ${file.name}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
        return;
      }
      setError(err);
      setStatus("error");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
        <DialogHeader>
          <DialogTitle>Upload PDF</DialogTitle>
          <DialogDescription className="dark:text-slate-300">
            Upload an EOB PDF to ingest claim data. This won&apos;t auto-apply to a
            draft yet.
          </DialogDescription>
        </DialogHeader>

        <div
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-center text-sm",
            isDragging
              ? "border-slate-400 bg-slate-50"
              : "border-slate-200 bg-slate-50",
            "dark:border-slate-700 dark:bg-slate-950"
          )}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            handleFile(event.dataTransfer.files?.[0]);
          }}
        >
          <CloudUpload className="h-6 w-6 text-slate-500" />
          <div className="text-slate-600 dark:text-slate-300">
            Drag & drop a PDF here, or click to browse.
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            aria-label="Upload PDF file"
            className="hidden"
            onChange={(event) => handleFile(event.target.files?.[0])}
          />
          <Button
            type="button"
            variant="outline"
            onClick={() => inputRef.current?.click()}
          >
            Choose PDF
          </Button>
          {file ? (
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Selected: {file.name}
            </div>
          ) : null}
        </div>

        {error ? <ErrorNotice error={error} /> : null}

        {response ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
            <div className="text-xs font-semibold uppercase text-slate-500">
              Response Preview
            </div>
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap">
              {JSON.stringify(response, null, 2)}
            </pre>
          </div>
        ) : null}

        <DialogFooter>
          <div className="mr-auto text-xs text-slate-500 dark:text-slate-400">
            Status: {status}
          </div>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button type="button" onClick={handleUpload} disabled={!file || status === "uploading"}>
            {status === "uploading" ? "Uploading..." : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
