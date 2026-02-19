import { Navigate, Route, Routes } from "react-router-dom";

import AdminPage from "@/pages/AdminPage";
import AdminPolicyRulesPage from "@/pages/AdminPolicyRulesPage";
import BootstrapPage from "@/pages/BootstrapPage";
import ChatPage from "@/pages/ChatPage";
import LoginPage from "@/pages/LoginPage";
import ProtectedRoute from "@/routes/ProtectedRoute";
import RoleRoute from "@/routes/RoleRoute";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/bootstrap" element={<BootstrapPage />} />
      <Route path="/app/dashboard" element={<Navigate to="/app/chat" replace />} />
      <Route
        path="/app/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin"
        element={
          <RoleRoute allowedRoles={["platform_staff_admin"]}>
            <AdminPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/admin/policy-rules"
        element={
          <RoleRoute allowedRoles={["platform_staff_admin"]}>
            <AdminPolicyRulesPage />
          </RoleRoute>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
