import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";

import { AuthProvider } from "@/lib/auth/AuthContext";
import AppRoutes from "@/routes/AppRoutes";

test("routes to /login", () => {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/login"]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>
  );

  expect(screen.getByText("Login")).toBeInTheDocument();
});
