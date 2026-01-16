import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type {
  InsuranceCompany,
  McpCode,
  PolicyLink,
} from "@/features/admin/api/client";
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
  id: 101,
  email: "admin@example.com",
  is_active: true,
  roles: ["admin", "doctor"],
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

  test("reference tab loads mcp codes and create works", async () => {
    const mcpCodes: McpCode[] = [
      {
        code: "99213",
        description: "Office visit",
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
      if (url.includes("/api/admin/mcp-codes") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: mcpCodes }));
      }
      if (url.endsWith("/api/admin/mcp-codes") && method === "POST") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as {
          code: string;
          description?: string | null;
        };
        const created: McpCode = {
          code: parsed.code,
          description: parsed.description ?? null,
        };
        mcpCodes.push(created);
        return Promise.resolve(buildJsonResponse({ status: 201, body: created }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    expect(
      await screen.findByRole("heading", { name: "MCP Codes" })
    ).toBeInTheDocument();
    expect(await screen.findByText("99213")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /new code/i }));
    await userEvent.type(screen.getByLabelText("Code"), "99001");
    await userEvent.type(screen.getByLabelText("Description"), "Office visit ext");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("99001")).toBeInTheDocument();
  });

  test("companies & policies loads policy links for selected company", async () => {
    const companies: InsuranceCompany[] = [
      {
        id: 11,
        name: "Alpha Health",
        created_at: "2026-01-01T00:00:00",
      },
    ];
    const mcpCodes: McpCode[] = [
      {
        code: "99213",
        description: "Office visit",
      },
    ];
    const policyLinks: PolicyLink[] = [
      {
        id: 21,
        insurance_company_id: 11,
        mcp_code: "99213",
        policy_url: "https://example.com/policy",
        created_at: "2026-01-01T00:00:00",
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
      if (url.endsWith("/api/admin/insurance-companies") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: companies }));
      }
      if (url.includes("/api/admin/mcp-codes") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: mcpCodes }));
      }
      if (url.includes("/api/admin/policy-links") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: policyLinks }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    const companiesTab = await screen.findByRole("button", {
      name: /companies & policies/i,
    });
    await userEvent.click(companiesTab);

    const agencyLabels = await screen.findAllByText("Alpha Health");
    expect(agencyLabels.length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText("https://example.com/policy")).toBeInTheDocument();
    });
  });

  test("company create omits slug field and submits without it", async () => {
    const companies: InsuranceCompany[] = [];
    const mcpCodes: McpCode[] = [];

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
      if (url.endsWith("/api/admin/insurance-companies") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: companies }));
      }
      if (url.endsWith("/api/admin/insurance-companies") && method === "POST") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as { name: string };
        const created: InsuranceCompany = {
          id: 12,
          name: parsed.name,
          created_at: "2026-01-03T00:00:00",
        };
        companies.push(created);
        return Promise.resolve(buildJsonResponse({ status: 201, body: created }));
      }
      if (url.includes("/api/admin/mcp-codes") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: mcpCodes }));
      }
      if (url.includes("/api/admin/policy-links") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    const companiesTab = await screen.findByRole("button", {
      name: /companies & policies/i,
    });
    await userEvent.click(companiesTab);

    await userEvent.click(await screen.findByRole("button", { name: "New" }));

    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.queryByLabelText("Slug")).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Name"), "Alpha Health");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    const agencyLabels = await screen.findAllByText("Alpha Health");
    expect(agencyLabels.length).toBeGreaterThan(0);
  });
});
