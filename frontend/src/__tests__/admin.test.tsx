import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AppRoutes from "@/routes/AppRoutes";
import { AuthProvider } from "@/lib/auth/AuthContext";
import type { AdminUser, Agency, PolicyLink, ProcedureCode } from "@/lib/api/admin";

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

const getIdFromUrl = (url: string): string => {
  const parsed = new URL(url, "http://localhost");
  const parts = parsed.pathname.split("/");
  return parts[parts.length - 1] ?? "";
};

const getPathFromUrl = (url: string): string => {
  return new URL(url, "http://localhost").pathname;
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

describe("admin catalog UI", () => {
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

  test("agencies load, create, edit", async () => {
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
      if (getPathFromUrl(url) === "/api/admin/agencies" && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({ status: 200, body: agencies.map((item) => ({ ...item })) })
        );
      }
      if (getPathFromUrl(url) === "/api/admin/agencies" && method === "POST") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as { name: string; slug: string; is_active: boolean };
        const created: Agency = {
          id: "agency-2",
          name: parsed.name,
          slug: parsed.slug,
          is_active: parsed.is_active,
          created_at: "2026-01-02T00:00:00",
          updated_at: "2026-01-02T00:00:00",
        };
        agencies.push(created);
        return Promise.resolve(buildJsonResponse({ status: 201, body: created }));
      }
      if (getPathFromUrl(url).startsWith("/api/admin/agencies/") && method === "PATCH") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as Partial<Agency>;
        const agencyId = getIdFromUrl(url);
        const agency = agencies.find((item) => item.id === agencyId);
        if (!agency) {
          return Promise.resolve(buildJsonResponse({ status: 404, body: { error: {} } }));
        }
        const updated = { ...agency, ...parsed, updated_at: "2026-01-03T00:00:00" };
        agencies.splice(agencies.indexOf(agency), 1, updated);
        return Promise.resolve(buildJsonResponse({ status: 200, body: updated }));
      }
      if (getPathFromUrl(url).startsWith("/api/admin/agencies/") && method === "DELETE") {
        const agencyId = getIdFromUrl(url);
        const index = agencies.findIndex((item) => item.id === agencyId);
        if (index >= 0) {
          agencies.splice(index, 1);
        }
        return Promise.resolve(buildJsonResponse({ status: 204, body: null }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    expect(await screen.findByText("Alpha Health")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /new agency/i }));
    await userEvent.type(screen.getByLabelText("Name"), "Beta Health");
    await userEvent.type(screen.getByLabelText("Slug"), "beta");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Beta Health")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /edit beta health/i }));
    const nameInput = screen.getByLabelText("Name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Beta Updated");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Beta Updated")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /delete beta updated/i }));
    await waitFor(() => {
      expect(screen.queryByText("Beta Updated")).not.toBeInTheDocument();
    });
  });

  test("policy links load, filter, create, edit", async () => {
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
    const codes: ProcedureCode[] = [
      {
        id: "code-1",
        code: "99213",
        title: "Office visit",
        category: "Evaluation",
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
        notes: null,
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
        return Promise.resolve(buildJsonResponse({ status: 200, body: codes }));
      }
      if (url.includes("/api/admin/policy-links") && method === "GET") {
        const queryText = url.split("?")[1] ?? "";
        if (queryText.includes("query=none")) {
          return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
        }
        return Promise.resolve(buildJsonResponse({ status: 200, body: policyLinks }));
      }
      if (url.endsWith("/api/admin/policy-links") && method === "POST") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as {
          agency_id: string;
          procedure_code_id: string;
          policy_url: string;
          status: "ACTIVE" | "INACTIVE";
        };
        const created: PolicyLink = {
          id: "link-2",
          agency_id: parsed.agency_id,
          procedure_code_id: parsed.procedure_code_id,
          policy_url: parsed.policy_url,
          effective_from: null,
          effective_to: null,
          status: parsed.status,
          notes: null,
          created_at: "2026-01-03T00:00:00",
          updated_at: "2026-01-03T00:00:00",
        };
        policyLinks.push(created);
        return Promise.resolve(buildJsonResponse({ status: 201, body: created }));
      }
      if (url.includes("/api/admin/policy-links/") && method === "PATCH") {
        const policyId = url.split("/").slice(-1)[0];
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as Partial<PolicyLink>;
        const existing = policyLinks.find((link) => link.id === policyId);
        if (!existing) {
          return Promise.resolve(buildJsonResponse({ status: 404, body: { error: {} } }));
        }
        const updated = { ...existing, ...parsed, updated_at: "2026-01-04T00:00:00" };
        policyLinks.splice(policyLinks.indexOf(existing), 1, updated);
        return Promise.resolve(buildJsonResponse({ status: 200, body: updated }));
      }
      if (url.includes("/api/admin/policy-links/") && method === "DELETE") {
        return Promise.resolve(buildJsonResponse({ status: 204, body: null }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    await screen.findByRole("button", { name: /policy links/i });
    await userEvent.click(screen.getByRole("button", { name: /policy links/i }));
    expect(await screen.findByText("https://example.com/policy")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Search"), "none");
    await userEvent.click(screen.getByRole("button", { name: /apply filters/i }));
    expect(await screen.findByText(/no policy links yet/i)).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("Search"));
    await userEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    await userEvent.click(screen.getByRole("button", { name: /new link/i }));
    const dialog = screen.getByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Agency"), "agency-1");
    await userEvent.selectOptions(within(dialog).getByLabelText("Procedure code"), "code-1");
    await userEvent.type(within(dialog).getByLabelText("Policy URL"), "https://example.com/new");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));

    expect(await screen.findByText("https://example.com/new")).toBeInTheDocument();

    const editButtons = screen.getAllByRole("button", { name: "Edit policy link" });
    const firstEdit = editButtons[0];
    if (!firstEdit) {
      throw new Error("Expected policy link edit button");
    }
    await userEvent.click(firstEdit);
    const editDialog = screen.getByRole("dialog");
    await userEvent.selectOptions(within(editDialog).getByLabelText("Status"), "INACTIVE");
    await userEvent.click(within(editDialog).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/admin/policy-links/link-1"),
        expect.objectContaining({ method: "PATCH" })
      );
    });
  });

  test("users load, create, edit, disable", async () => {
    const agencies: Agency[] = [];
    const users: AdminUser[] = [
      {
        id: "user-1",
        email: "alpha@example.com",
        full_name: "Alpha User",
        tenant_id: adminUser.tenant_id,
        is_active: true,
        is_admin: false,
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
      if (url.endsWith("/api/admin/agencies") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: agencies }));
      }
      if (url.includes("/api/admin/users") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: users }));
      }
      if (url.endsWith("/api/admin/users") && method === "POST") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as {
          email: string;
          full_name?: string | null;
          is_admin: boolean;
          is_active: boolean;
        };
        const created: AdminUser = {
          id: "user-2",
          email: parsed.email,
          full_name: parsed.full_name ?? null,
          tenant_id: adminUser.tenant_id,
          is_active: parsed.is_active,
          is_admin: parsed.is_admin,
          created_at: "2026-01-02T00:00:00",
        };
        users.push(created);
        return Promise.resolve(buildJsonResponse({ status: 201, body: created }));
      }
      if (url.includes("/api/admin/users/") && method === "PATCH") {
        const userId = getIdFromUrl(url);
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as Partial<AdminUser>;
        const existing = users.find((item) => item.id === userId);
        if (!existing) {
          return Promise.resolve(buildJsonResponse({ status: 404, body: { error: {} } }));
        }
        const updated: AdminUser = { ...existing, ...parsed };
        users.splice(users.indexOf(existing), 1, updated);
        return Promise.resolve(buildJsonResponse({ status: 200, body: updated }));
      }
      if (url.includes("/reset-password") && method === "POST") {
        return Promise.resolve(buildJsonResponse({ status: 204, body: null }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    await userEvent.click(await screen.findByRole("button", { name: /users/i }));
    expect(await screen.findByText("alpha@example.com")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /new user/i }));
    await userEvent.type(screen.getByLabelText("Email"), "beta@example.com");
    await userEvent.type(screen.getByLabelText("Full name"), "Beta User");
    await userEvent.type(screen.getByLabelText("Password"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("beta@example.com")).toBeInTheDocument();

    const editButtons = screen.getAllByRole("button", { name: "Edit user" });
    const firstEdit = editButtons[0];
    if (!firstEdit) {
      throw new Error("Expected edit user button");
    }
    await userEvent.click(firstEdit);
    const nameInput = screen.getByLabelText("Full name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Alpha Updated");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Alpha Updated")).toBeInTheDocument();

    const alphaRow = screen.getByText("alpha@example.com").closest("tr");
    if (!alphaRow) {
      throw new Error("Expected user row for alpha@example.com");
    }
    await userEvent.click(within(alphaRow).getByRole("button", { name: "Disable" }));
    expect(await within(alphaRow).findByText("Disabled")).toBeInTheDocument();
  });

  test("policy links show missing indicator when flagged", async () => {
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
    const codes: ProcedureCode[] = [
      {
        id: "code-1",
        code: "99213",
        title: "Office visit",
        category: "Evaluation",
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
        missing_policy_link: true,
        effective_from: null,
        effective_to: null,
        status: "ACTIVE",
        notes: null,
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
        return Promise.resolve(buildJsonResponse({ status: 200, body: codes }));
      }
      if (url.includes("/api/admin/policy-links") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: policyLinks }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    await screen.findByRole("button", { name: /policy links/i });
    await userEvent.click(screen.getByRole("button", { name: /policy links/i }));

    expect(await screen.findByText("Missing")).toBeInTheDocument();
  });
});
