import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { AuthProvider } from "@/lib/auth/AuthContext";
import AppRoutes from "@/routes/AppRoutes";

type JsonResponseInit = {
  status: number;
  body: unknown;
  requestId?: string;
};

const buildJsonResponse = ({ status, body, requestId }: JsonResponseInit): Response => {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId ?? "req-test",
    },
  });
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

describe("auth flow", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    localStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("login success stores token and redirects", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const method = init?.method ?? "GET";
      if (url.endsWith("/auth/login")) {
        return Promise.resolve(
          buildJsonResponse({
            status: 200,
            body: { access_token: "token-123", token_type: "bearer" },
          })
        );
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
      if (url.endsWith("/api/dashboard/doctor") && method === "GET") {
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
      return Promise.reject(new Error("unexpected request"));
    });

    renderWithProviders(["/login"]);

    await userEvent.type(screen.getByLabelText(/email/i), "doctor@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "secret");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      const stored = localStorage.getItem("sphereapp_token");
      expect(stored).not.toBeNull();
    });

    expect(await screen.findByText(/Dashboard/i)).toBeInTheDocument();
  });

  test("login failure shows error", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        status: 401,
        body: {
          error: {
            code: "HTTP_401",
            message: "HTTP error",
            details: { detail: "Invalid credentials" },
          },
        },
        requestId: "req-login-fail",
      })
    );

    renderWithProviders(["/login"]);

    await userEvent.type(screen.getByLabelText(/email/i), "doctor@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/Error: HTTP_401/)).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-login-fail/)).toBeInTheDocument();
  });

  test("protected route redirects to login when unauthenticated", () => {
    renderWithProviders(["/app/chat"]);

    expect(screen.getByText("Login")).toBeInTheDocument();
  });
});
