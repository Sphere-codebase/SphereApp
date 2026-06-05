import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type {
  AdminClaimSummary,
  AdminUser,
  ClaimStediData,
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
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

const adminUser = {
  id: 101,
  email: "admin@example.com",
  full_name: "Admin User",
  role: "platform_staff_admin",
  clinic_id: 1,
  clinic_name: "Test Clinic",
  is_active: true,
};

const buildClaimSummary = (): AdminClaimSummary => ({
  id: 501,
  patient_id: 301,
  patient_name: "Jane Doe",
  doctor_id: 202,
  insurance_company_id: 11,
  insurance_company_name: "Alpha Health",
  claim_number: "CLM-501",
  claim_status: "SUBMITTED",
  service_date: "2025-06-30",
  claim_date: "2025-07-01",
  submitted_at: null,
  billed_amount_total: 267.54,
  allowed_amount_total: null,
  coinsurance_amount_total: null,
  copay_amount_total: null,
  deductible_amount_total: null,
  stedi_status: null,
  stedi_status_code: null,
  stedi_status_category: null,
  stedi_status_message: null,
  stedi_amount_paid: null,
  stedi_checked_at: null,
  stedi_payer_claim_number: null,
  created_at: "2026-01-01T00:00:00Z",
});

const buildClaimStediData = (
  overrides: Partial<ClaimStediData> = {}
): ClaimStediData => ({
  claim_id: 501,
  insurance_company: {
    id: 11,
    name: "Alpha Health",
    stedi_trading_partner_service_id: null,
  },
  patient_insurance_policy: {
    id: 401,
    member_id: null,
    group_number: null,
  },
  clinic: {
    billing_provider_organization_name: null,
    billing_provider_npi: null,
    billing_provider_tax_id: null,
  },
  ...overrides,
});

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
      name: /companies/i,
    });
    await userEvent.click(companiesTab);

    const agencyLabels = await screen.findAllByText("Alpha Health");
    expect(agencyLabels.length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText("Office visit")).toBeInTheDocument();
      expect(screen.queryByText("https://example.com/policy")).not.toBeInTheDocument();
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
      name: /companies/i,
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

  test("policy rules page loads for admin", async () => {
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
      if (url.endsWith("/api/admin/policy-links/21/rules") && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              policy_rules_id: 55,
              policy_link_id: 21,
              extracted_at: "2026-01-02T00:00:00",
              title: "Policy title",
              next_review_iso: "2026-08-13",
              criteria_json: [
                {
                  id: "MN-1",
                  text: "Criterion",
                  children: [],
                },
              ],
              notes_json: [{ text: "Note text" }],
              medical_necessity_clean: "Medical necessity text",
            },
          })
        );
      }
      if (url.includes("/api/admin/policy-links") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: policyLinks }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    const companiesTab = await screen.findByRole("button", {
      name: /companies/i,
    });
    await userEvent.click(companiesTab);

    await screen.findByText("Office visit");
    expect(screen.queryByText("https://example.com/policy")).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /refresh rules/i })
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /view rules/i }));

    expect(
      await screen.findByRole("heading", { name: /policy rules/i })
    ).toBeInTheDocument();
    expect(await screen.findByText("Policy title")).toBeInTheDocument();
    expect(await screen.findByText("Medical necessity text")).toBeInTheDocument();
  });

  test("non-admin does not see policy rule buttons", async () => {
    const memberUser = {
      id: 202,
      email: "doctor@example.com",
      full_name: "Doctor User",
      role: "doctor",
      clinic_id: 1,
      clinic_name: "Test Clinic",
      is_active: true,
    };

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(buildJsonResponse({ status: 200, body: memberUser }));
      }
      if (url.includes("/api/chat/sessions") && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: [
              {
                id: 1,
                doctor_id: 202,
                created_at: "2026-02-19T10:00:00Z",
                claim_id: null,
                patient_id: null,
                title: "Test Session",
              },
            ],
          })
        );
      }
      if (url.includes("/api/chat/sessions/1/messages") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    expect(await screen.findByText(/Dashboard/i)).toBeInTheDocument();
  });

  test("dashboard claim status refresh updates payer status", async () => {
    const claims: AdminClaimSummary[] = [
      {
        id: 501,
        patient_id: 301,
        patient_name: "Jane Doe",
        doctor_id: 202,
        insurance_company_id: 11,
        insurance_company_name: "Alpha Health",
        claim_number: "CLM-501",
        claim_status: "SUBMITTED",
        service_date: "2025-06-30",
        claim_date: "2025-07-01",
        billed_amount_total: 267.54,
        allowed_amount_total: null,
        coinsurance_amount_total: null,
        copay_amount_total: null,
        deductible_amount_total: null,
        stedi_status: null,
        stedi_status_code: null,
        stedi_status_category: null,
        stedi_status_message: null,
        stedi_amount_paid: null,
        stedi_checked_at: null,
        stedi_payer_claim_number: null,
        created_at: "2026-01-01T00:00:00Z",
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
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.endsWith("/api/admin/patients") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.includes("/api/admin/claims") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: claims }));
      }
      if (url.endsWith("/api/claims/501/refresh-status") && method === "POST") {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              claim_id: 501,
              status: "PAID",
              status_code: "65",
              status_category: "F1",
              message: "Claim/line has been paid.",
              amount_paid: 108.77,
              checked_at: "2026-06-04T12:00:00Z",
              payer_claim_number: "PAYER-501",
            },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);
    await userEvent.click(await screen.findByRole("button", { name: /dashboard/i }));
    expect(await screen.findByText("Jane Doe")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /update status/i }));

    expect(await screen.findByText("PAID")).toBeInTheDocument();
    expect(await screen.findByText("Claim status updated.")).toBeInTheDocument();
  });

  test("missing Stedi data response opens modal with requested sections", async () => {
    const claims: AdminClaimSummary[] = [buildClaimSummary()];

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
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.endsWith("/api/admin/patients") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.includes("/api/admin/claims") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: claims }));
      }
      if (url.endsWith("/api/claims/501/refresh-status") && method === "POST") {
        return Promise.resolve(
          buildJsonResponse({
            status: 422,
            body: {
              error: {
                code: "STEDI_MISSING_REQUIRED_DATA",
                message: "Required claim status fields are missing.",
                details: {
                  missing: [
                    {
                      field: "insurance_company.stedi_trading_partner_service_id",
                      message: "Set the payer Stedi trading partner service ID.",
                    },
                    {
                      field: "patient_insurance_policy.member_id",
                      message: "Set the patient's member ID for this payer.",
                    },
                    {
                      field: "clinic.billing_provider",
                      message: "Set clinic billing provider.",
                    },
                  ],
                },
              },
            },
          })
        );
      }
      if (url.endsWith("/api/claims/501/stedi-data") && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({ status: 200, body: buildClaimStediData() })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);
    await userEvent.click(await screen.findByRole("button", { name: /dashboard/i }));
    await userEvent.click(await screen.findByRole("button", { name: /update status/i }));

    expect(
      await screen.findByRole("heading", { name: "Missing Stedi data" })
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Stedi payer ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Member ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Billing provider organization name")).toBeInTheDocument();
    expect(screen.getByText("Stedi payer ID is required for payer matching.")).toBeInTheDocument();
    expect(
      screen.getByText("Member ID should match the patient’s insurance card.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Billing provider requires organization name and NPI or Tax ID.")
    ).toBeInTheDocument();
  });

  test("missing Stedi data modal hides sections not returned by API", async () => {
    const claims: AdminClaimSummary[] = [buildClaimSummary()];

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
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.endsWith("/api/admin/patients") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.includes("/api/admin/claims") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: claims }));
      }
      if (url.endsWith("/api/claims/501/refresh-status") && method === "POST") {
        return Promise.resolve(
          buildJsonResponse({
            status: 422,
            body: {
              error: {
                code: "STEDI_MISSING_REQUIRED_DATA",
                message: "Required claim status fields are missing.",
                details: {
                  missing: [
                    {
                      field: "patient_insurance_policy.member_id",
                      message: "Set the patient's member ID for this payer.",
                    },
                  ],
                },
              },
            },
          })
        );
      }
      if (url.endsWith("/api/claims/501/stedi-data") && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: buildClaimStediData({
              insurance_company: {
                id: 11,
                name: "Alpha Health",
                stedi_trading_partner_service_id: "87726",
              },
              clinic: {
                billing_provider_organization_name: "Billing LLC",
                billing_provider_npi: "1999999984",
                billing_provider_tax_id: null,
              },
            }),
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);
    await userEvent.click(await screen.findByRole("button", { name: /dashboard/i }));
    await userEvent.click(await screen.findByRole("button", { name: /update status/i }));

    expect(await screen.findByLabelText("Member ID")).toBeInTheDocument();
    expect(screen.queryByLabelText("Stedi payer ID")).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Billing provider organization name")
    ).not.toBeInTheDocument();
  });

  test("save and retry updates APIs before refreshing claim status again", async () => {
    const claims: AdminClaimSummary[] = [buildClaimSummary()];
    let refreshCount = 0;
    const patchBodies: unknown[] = [];

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
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.endsWith("/api/admin/patients") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.includes("/api/admin/claims") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: claims }));
      }
      if (url.endsWith("/api/claims/501/refresh-status") && method === "POST") {
        refreshCount += 1;
        if (refreshCount === 1) {
          return Promise.resolve(
            buildJsonResponse({
              status: 422,
              body: {
                error: {
                  code: "STEDI_MISSING_REQUIRED_DATA",
                  message: "Required claim status fields are missing.",
                  details: {
                    missing: [
                      {
                        field: "insurance_company.stedi_trading_partner_service_id",
                        message: "Set the payer Stedi trading partner service ID.",
                      },
                      {
                        field: "patient_insurance_policy.member_id",
                        message: "Set the patient's member ID for this payer.",
                      },
                    ],
                  },
                },
              },
            })
          );
        }
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: {
              claim_id: 501,
              status: "PAID",
              status_code: "65",
              status_category: "F1",
              message: "Claim/line has been paid.",
              amount_paid: 108.77,
              checked_at: "2026-06-04T12:00:00Z",
              payer_claim_number: "PAYER-501",
            },
          })
        );
      }
      if (url.endsWith("/api/claims/501/stedi-data") && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({ status: 200, body: buildClaimStediData() })
        );
      }
      if (url.endsWith("/api/claims/501/stedi-data") && method === "PATCH") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        patchBodies.push(JSON.parse(bodyText));
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: buildClaimStediData({
              insurance_company: {
                id: 11,
                name: "Alpha Health",
                stedi_trading_partner_service_id: "005010",
              },
              patient_insurance_policy: {
                id: 401,
                member_id: "MEM-123",
                group_number: "GRP-9",
              },
            }),
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);
    await userEvent.click(await screen.findByRole("button", { name: /dashboard/i }));
    await userEvent.click(await screen.findByRole("button", { name: /update status/i }));
    await userEvent.type(await screen.findByLabelText("Stedi payer ID"), "005010");
    await userEvent.type(screen.getByLabelText("Member ID"), "MEM-123");
    await userEvent.type(screen.getByLabelText("Group number"), "GRP-9");
    await userEvent.click(
      screen.getByRole("button", { name: "Save and retry status update" })
    );

    await waitFor(() => expect(refreshCount).toBe(2));
    expect(patchBodies).toEqual([
      {
        insurance_company: {
          stedi_trading_partner_service_id: "005010",
        },
        patient_insurance_policy: {
          member_id: "MEM-123",
          group_number: "GRP-9",
        },
      },
    ]);
    expect(await screen.findByText("PAID")).toBeInTheDocument();
  });

  test("missing Stedi data modal shows safe load errors", async () => {
    const claims: AdminClaimSummary[] = [buildClaimSummary()];

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
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.endsWith("/api/admin/patients") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.includes("/api/admin/claims") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: claims }));
      }
      if (url.endsWith("/api/claims/501/refresh-status") && method === "POST") {
        return Promise.resolve(
          buildJsonResponse({
            status: 422,
            body: {
              error: {
                code: "STEDI_MISSING_REQUIRED_DATA",
                message: "Required claim status fields are missing.",
                details: {
                  missing: [
                    {
                      field: "insurance_company.stedi_trading_partner_service_id",
                      message: "Set the payer Stedi trading partner service ID.",
                    },
                  ],
                },
              },
            },
          })
        );
      }
      if (url.endsWith("/api/claims/501/stedi-data") && method === "GET") {
        return Promise.resolve(
          buildJsonResponse({
            status: 500,
            body: {
              error: {
                code: "INTERNAL_ERROR",
                message: "server included sensitive raw detail",
                details: {},
              },
            },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);
    await userEvent.click(await screen.findByRole("button", { name: /dashboard/i }));
    await userEvent.click(await screen.findByRole("button", { name: /update status/i }));

    expect(
      await screen.findByRole("heading", { name: "Missing Stedi data" })
    ).toBeInTheDocument();
    expect(screen.getByText("Could not load current Stedi data.")).toBeInTheDocument();
    expect(screen.queryByText("server included sensitive raw detail")).not.toBeInTheDocument();
  });

  test("users tab shows current account marker and allows changing another user's role", async () => {
    const users: AdminUser[] = [
      {
        id: 101,
        email: "admin@example.com",
        full_name: "Admin User",
        is_active: true,
        role: "platform_staff_admin",
        roles: ["platform_staff_admin"],
        created_at: "2026-02-01T00:00:00Z",
      },
      {
        id: 303,
        email: "doctor@example.com",
        full_name: "Doctor User",
        is_active: true,
        role: "doctor",
        roles: ["doctor"],
        created_at: "2026-02-01T00:00:00Z",
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
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      if (url.endsWith("/api/admin/users") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: users }));
      }
      if (url.endsWith("/api/admin/users/303") && method === "PATCH") {
        const bodyText = typeof init?.body === "string" ? init.body : "{}";
        const parsed = JSON.parse(bodyText) as { roles?: string[] };
        users[1] = {
          ...users[1],
          role: (parsed.roles?.[0] as AdminUser["role"] | undefined) ?? users[1].role,
          roles: parsed.roles ?? users[1].roles,
        };
        return Promise.resolve(buildJsonResponse({ status: 200, body: users[1] }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    await userEvent.click(await screen.findByRole("button", { name: /users/i }));

    expect(await screen.findByText("You")).toBeInTheDocument();
    expect(screen.getAllByText("Platform Staff Admin").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Doctor").length).toBeGreaterThan(0);
    expect(screen.queryByLabelText("Role for admin@example.com")).not.toBeInTheDocument();

    const roleSelect = screen.getByLabelText("Role for doctor@example.com");
    await userEvent.selectOptions(roleSelect, "clinic_admin");
    await userEvent.click(
      screen.getByRole("button", { name: "Save role for doctor@example.com" })
    );

    await waitFor(() => {
      expect(screen.getAllByText("Clinic Admin").length).toBeGreaterThan(0);
    });
  });

  test("non-platform admins do not see the users tab", async () => {
    const clinicAdminUser = {
      id: 404,
      email: "clinic-admin@example.com",
      full_name: "Clinic Admin",
      role: "clinic_admin",
      clinic_id: 1,
      clinic_name: "Test Clinic",
      is_active: true,
    };

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/me")) {
        return Promise.resolve(buildJsonResponse({ status: 200, body: clinicAdminUser }));
      }
      if (url.includes("/api/admin/mcp-codes") && method === "GET") {
        return Promise.resolve(buildJsonResponse({ status: 200, body: [] }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    renderWithProviders(["/app/admin"]);

    expect(await screen.findByRole("heading", { name: "MCP Codes" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /users/i })).not.toBeInTheDocument();
  });
});
