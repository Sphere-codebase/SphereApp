import { Navigate, Route, Routes } from "react-router-dom";

import AdminPage from "@/pages/AdminPage";
import AdminPolicyRulesPage from "@/pages/AdminPolicyRulesPage";
import BootstrapPage from "@/pages/BootstrapPage";
import ChatPage from "@/pages/ChatPage";
import DoctorDashboardPage from "@/pages/DoctorDashboardPage";
import LoginPage from "@/pages/LoginPage";
import ProtectedRoute from "@/routes/ProtectedRoute";
import RoleRoute from "@/routes/RoleRoute";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/bootstrap" element={<BootstrapPage />} />
      <Route
        path="/app/dashboard"
        element={
          <ProtectedRoute>
            <DoctorDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/chat"
        element={
          <RoleRoute allowedRoles={["doctor", "chief_doctor", "clinic_admin"]}>
            <ChatPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/workspace"
        element={
          <RoleRoute allowedRoles={["doctor", "chief_doctor", "clinic_admin"]}>
            <ChatPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/workspace/:sessionId"
        element={
          <RoleRoute allowedRoles={["doctor", "chief_doctor", "clinic_admin"]}>
            <ChatPage />
          </RoleRoute>
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
