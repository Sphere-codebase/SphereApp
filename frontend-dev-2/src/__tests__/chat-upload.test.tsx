import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import ChatPage from "@/pages/ChatPage";
import { AuthProvider } from "@/lib/auth/AuthContext";

type JsonResponseInit = {
  status: number;
  body: unknown;
  requestId?: string;
};

const buildJsonResponse = ({ status, body, requestId }: JsonResponseInit): Response => {
  const headers = new Headers({ "X-Request-ID": requestId ?? "req-test" });
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { status, headers });
};

const renderWithProviders = () => {
  return render(
    <AuthProvider>
      <MemoryRouter>
        <ChatPage />
      </MemoryRouter>
    </AuthProvider>
  );
};

describe("chat pdf upload", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(
      "sphereapp_token",
      JSON.stringify({ accessToken: "token-123", tokenType: "bearer" })
    );
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("shows summary after upload and can close", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              id: 1,
              email: "doctor@example.com",
              is_active: true,
              roles: ["doctor"],
            },
          })
        );
      }
      if (url.endsWith("/api/chat/sessions") && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: [{ id: 1, doctor_id: 1, created_at: "2026-01-01T00:00:00" }],
          })
        );
      }
      if (url.endsWith("/api/chat/sessions/1/messages") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.endsWith("/api/claims/ingest-pdf") && method === "POST") {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              claim_id: 44,
              patient_id: 12,
              session_id: 1,
              patient_name: "Lloyd Goldfarb",
              patient_date_of_birth: "1964-10-15",
              account_number: "060391381674",
              service_date: "2025-07-09",
              line_count: 4,
              total_billed_cents: 370000,
              total_allowed_cents: 45234,
              total_paid_cents: 36187,
            },
          })
        );
      }
      if (url.endsWith("/health")) {
        return Promise.resolve(new Response("", { status: 200 }));
      }
      if (url.endsWith("/ready")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: { checks: { db: "ok", llm: "ok" } },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders();

    const fileInput = await screen.findByLabelText("Upload PDF");
    const file = new File(["pdf"], "claim.pdf", { type: "application/pdf" });
    await userEvent.upload(fileInput, file);

    expect(await screen.findByText("Claim summary")).toBeInTheDocument();
    expect(await screen.findByText("Lloyd Goldfarb")).toBeInTheDocument();
    expect(await screen.findByText("Total billed: $3,700.00")).toBeInTheDocument();
    expect(screen.queryByText("Account:")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /close claim summary/i }));
    expect(await screen.findByText("Upload PDF")).toBeInTheDocument();
  });
});
