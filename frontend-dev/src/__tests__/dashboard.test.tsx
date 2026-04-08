import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { AuthProvider } from "@/lib/auth/AuthContext";
import AppRoutes from "@/routes/AppRoutes";

type JsonResponseInit = {
  status: number;
  body: unknown;
  requestId?: string;
};

function buildJsonResponse({ status, body, requestId }: JsonResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId ?? "req-test",
    },
  });
}

function renderWithProviders(initialEntries: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <PathProbe />
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function PathProbe() {
  const location = useLocation();
  return <div data-testid="current-path">{location.pathname}</div>;
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
}

function statusResponse(url: string): Response | null {
  if (url.endsWith("/health")) {
    return buildJsonResponse({ status: 200, body: { ok: true } });
  }
  if (url.endsWith("/ready")) {
    return buildJsonResponse({
      status: 200,
      body: { checks: { db: "ok", llm: "ok" } },
    });
  }
  return null;
}

describe("dashboard routing", () => {
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

  test("doctor dashboard loads the doctor endpoint and renders empty state", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      const status = statusResponse(url);
      if (status) {
        return Promise.resolve(status);
      }
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              id: 7,
              email: "doctor@example.com",
              full_name: "Doc One",
              role: "doctor",
              clinic_id: 1,
              clinic_name: "Test Clinic",
              is_active: true,
            },
          })
        );
      }
      if (url.endsWith("/api/dashboard/doctor")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              doctor: { id: 7, full_name: "Doc One" },
              active_sessions: [],
              recent_claims: [],
            },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/dashboard"]);

    expect(await screen.findByText("No active sessions yet.")).toBeInTheDocument();
    expect(screen.getByText("No recent claims yet.")).toBeInTheDocument();
    expect(screen.getByTestId("current-path")).toHaveTextContent("/app/dashboard");

    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).endsWith("/api/dashboard/doctor"))
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).includes("/api/clinic/dashboard"))
    ).toBe(false);
  });

  test("clinic admin dashboard uses the clinic endpoint with live query params", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      const status = statusResponse(url);
      if (status) {
        return Promise.resolve(status);
      }
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              id: 9,
              email: "clinic-admin@example.com",
              full_name: "Clinic Admin",
              role: "clinic_admin",
              clinic_id: 1,
              clinic_name: "Test Clinic",
              is_active: true,
            },
          })
        );
      }
      if (url.includes("/api/clinic/dashboard")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              range: { from: "2026-03-09", to: "2026-04-08" },
              kpis: {
                total_claims: 0,
                draft_claims: 0,
                finalized_claims: 0,
                active_doctors: 0,
              },
              top_insurers: [],
              claims_timeseries: [],
              ai_timeseries: [],
              recent_activity: [],
            },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/dashboard"]);

    expect(await screen.findByRole("heading", { name: "Clinic Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("No insurer data.")).toBeInTheDocument();
    expect(screen.getByTestId("current-path")).toHaveTextContent("/app/dashboard");

    await waitFor(() => {
      const clinicCall = fetchMock.mock.calls.find(([input]) =>
        requestUrl(input).includes("/api/clinic/dashboard")
      );
      expect(clinicCall).toBeDefined();
      expect(requestUrl(clinicCall![0])).toContain("/api/clinic/dashboard?from=");
      expect(requestUrl(clinicCall![0])).toContain("&to=");
    });

    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).endsWith("/api/dashboard/doctor"))
    ).toBe(false);
  });

  test("chief doctor can open dashboard and stays on the clinic dashboard route", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      const status = statusResponse(url);
      if (status) {
        return Promise.resolve(status);
      }
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              id: 10,
              email: "chief@example.com",
              full_name: "Chief Doctor",
              role: "chief_doctor",
              clinic_id: 1,
              clinic_name: "Test Clinic",
              is_active: true,
            },
          })
        );
      }
      if (url.includes("/api/clinic/dashboard")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              range: { from: "2026-03-09", to: "2026-04-08" },
              kpis: {
                total_claims: 0,
                draft_claims: 0,
                finalized_claims: 0,
                active_doctors: 0,
              },
              top_insurers: [],
              claims_timeseries: [],
              ai_timeseries: [],
              recent_activity: [],
            },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/dashboard"]);

    expect(await screen.findByRole("heading", { name: "Clinic Dashboard" })).toBeInTheDocument();
    expect(screen.getByTestId("current-path")).toHaveTextContent("/app/dashboard");
    expect(screen.queryByRole("heading", { name: "MCP Codes" })).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).includes("/api/clinic/dashboard"))
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).endsWith("/api/dashboard/doctor"))
    ).toBe(false);
  });

  test("platform staff admin stays on dashboard and sees real platform usage data", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      const status = statusResponse(url);
      if (status) {
        return Promise.resolve(status);
      }
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              id: 11,
              email: "platform@example.com",
              full_name: "Platform Admin",
              role: "platform_staff_admin",
              clinic_id: 1,
              clinic_name: "Test Clinic",
              is_active: true,
            },
          })
        );
      }
      if (url.includes("/api/platform/clinics")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              items: [
                {
                  id: 1,
                  name: "Test Clinic",
                  is_blocked: false,
                  created_at: "2026-01-01T00:00:00Z",
                  counters: {
                    doctors_count: 3,
                    patients_count: 12,
                    claims_30d: 9,
                  },
                },
              ],
              limit: 100,
              offset: 0,
              total: 1,
            },
          })
        );
      }
      if (url.includes("/api/platform/usage")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              range: { from: "2026-03-09", to: "2026-04-08" },
              scope: { clinic_id: null },
              kpis: {
                claims_created: 12,
                claims_finalized: 8,
                pdf_generated: 5,
                ai_actions: 19,
                active_clinics: 4,
              },
              timeseries: {
                claims: [{ date: "2026-04-08", count: 3 }],
                pdf: [{ date: "2026-04-08", count: 1 }],
                ai: [{ date: "2026-04-08", count: 4 }],
              },
              top_clinics: [
                {
                  clinic_id: 1,
                  clinic_name: "Test Clinic",
                  claims: 12,
                  pdf: 5,
                  ai: 19,
                },
              ],
            },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/dashboard"]);

    expect(await screen.findByText("Claims Created")).toBeInTheDocument();
    expect(screen.getByText("Claims Finalized")).toBeInTheDocument();
    expect(screen.getByText("Top Clinics by Usage")).toBeInTheDocument();
    expect(screen.getByText("Test Clinic")).toBeInTheDocument();
    expect(screen.getByTestId("current-path")).toHaveTextContent("/app/dashboard");
    expect(screen.queryByRole("heading", { name: "MCP Codes" })).not.toBeInTheDocument();
    expect(
      screen.queryByText("A dedicated platform dashboard is not available yet for this role.")
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).endsWith("/api/dashboard/doctor"))
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([input]) => requestUrl(input).includes("/api/platform/usage"))
    ).toBe(true);
  });
});
