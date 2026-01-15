import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { Agency, PolicyLink, ProcedureCode } from "@/features/admin/api/client";
import { AuthProvider } from "@/lib/auth/AuthContext";
import AppRoutes from "@/routes/AppRoutes";

type JsonResponseInit = {
  status: number;
  body: unknown;
  requestId?: string;
};

const buildJsonResponse = ({ status, body, requestId }: JsonResponseInit): Response => {
  const headers = new Headers({ "X-Request-ID": requestId ?? "req-test" });
  if (status === 204) {
    return new Response(null, { status, headers });
  }
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { status, headers });
};

const renderWithProviders = (initialEntries: string[]) => {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>
  );
};

const adminUser = {
  id: "4c1d6926-8afc-42cc-a1a0-05cb8b10a1f8",
  email: "admin@example.com",
  tenant_id: "0d0f88a4-81b0-4c87-95db-32b0b45f5c09",
  is_active: true,
  is_admin: true,
};

describe("admin ui", () => {
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

  test("reference tab loads procedure codes and create works", async () => {
    const procedureCodes: ProcedureCode[] = [
      {
        id: "code-1",
        code: "99213",
        title: "Office visit",
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(buildJsonResponse({ status: 200, body: adminUser }));
      }
      if (url.includes("/api/admin/procedure-codes") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: procedureCodes }));
      }
      if (url.endsWith("/api/admin/procedure-codes") && method === "POST") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as {
          code: string;
          title?: string | null;
        };
        const created: ProcedureCode = {
          id: "code-2",
          code: parsed.code,
          title: parsed.title ?? null,
          created_at: "2026-01-02T00:00:00",
          updated_at: "2026-01-02T00:00:00",
        };
        procedureCodes.push(created);
        return Promise.resolve(buildJsonResponse({ status: 201, body: created }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    expect(
      await screen.findByRole("heading", { name: "Procedure Codes" })
    ).toBeInTheDocument();
    expect(await screen.findByText("99213")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /new code/i }));
    await userEvent.type(screen.getByLabelText("Code"), "99001");
    await userEvent.type(screen.getByLabelText("Title"), "Office visit ext");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("99001")).toBeInTheDocument();
  });

  test("agencies & policies loads policy links for selected agency", async () => {
    const agencies: Agency[] = [
      {
        id: "agency-1",
        name: "Alpha Health",
        slug: "alpha",
        is_active: true,
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
    ];
    const procedureCodes: ProcedureCode[] = [
      {
        id: "code-1",
        code: "99213",
        title: "Office visit",
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-01T00:00:00",
      },
    ];
    const policyLinks: PolicyLink[] = [
      {
        id: "link-1",
        agency_id: "agency-1",
        procedure_code_id: "code-1",
        policy_url: "https://example.com/policy",
        effective_from: null,
        effective_to: null,
        status: "ACTIVE",
        notes: "Coverage details",
        created_at: "2026-01-01T00:00:00",
        updated_at: "2026-01-02T00:00:00",
      },
    ];

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(buildJsonResponse({ status: 200, body: adminUser }));
      }
      if (url.endsWith("/api/admin/agencies") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: agencies }));
      }
      if (url.includes("/api/admin/procedure-codes") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: procedureCodes }));
      }
      if (url.includes("/api/admin/policy-links") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: policyLinks }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    const agenciesTab = await screen.findByRole("button", {
      name: /agencies & policies/i,
    });
    await userEvent.click(agenciesTab);

    const agencyLabels = await screen.findAllByText("Alpha Health");
    expect(agencyLabels.length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText("https://example.com/policy")).toBeInTheDocument();
    });
  });

  test("agency create hides slug field and submits without it", async () => {
    const agencies: Agency[] = [];
    const procedureCodes: ProcedureCode[] = [];

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(buildJsonResponse({ status: 200, body: adminUser }));
      }
      if (url.endsWith("/api/admin/agencies") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: agencies }));
      }
      if (url.endsWith("/api/admin/agencies") && method === "POST") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as { name: string; is_active?: boolean };
        const created: Agency = {
          id: "agency-1",
          name: parsed.name,
          slug: "alpha-health",
          is_active: parsed.is_active ?? true,
          created_at: "2026-01-03T00:00:00",
          updated_at: "2026-01-03T00:00:00",
        };
        agencies.push(created);
        return Promise.resolve(buildJsonResponse({ status: 201, body: created }));
      }
      if (url.includes("/api/admin/procedure-codes") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: procedureCodes }));
      }
      if (url.includes("/api/admin/policy-links") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    const agenciesTab = await screen.findByRole("button", {
      name: /agencies & policies/i,
    });
    await userEvent.click(agenciesTab);

    await userEvent.click(await screen.findByRole("button", { name: "New" }));

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.queryByLabelText("Slug")).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Name"), "Alpha Health");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    const agencyLabels = await screen.findAllByText("Alpha Health");
    expect(agencyLabels.length).toBeGreaterThan(0);
  });
});
