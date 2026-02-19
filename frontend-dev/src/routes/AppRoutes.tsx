import { Navigate, Route, Routes } from "react-router-dom";

import AdminPage from "@/pages/AdminPage";
import AdminPolicyRulesPage from "@/pages/AdminPolicyRulesPage";
import AIHistoryPage from "@/pages/AIHistoryPage";
import BootstrapPage from "@/pages/BootstrapPage";
import ChatPage from "@/pages/ChatPage";
import DoctorDashboardPage from "@/pages/DoctorDashboardPage";
import InsuranceRulesPage from "@/pages/InsuranceRulesPage";
import LoginPage from "@/pages/LoginPage";
import PatientProfilePage from "@/pages/PatientProfilePage";
import PatientsListPage from "@/pages/PatientsListPage";
import ClinicDashboardPage from "@/pages/ClinicDashboardPage";
import ClinicDoctorsPage from "@/pages/ClinicDoctorsPage";
import ClinicAuditLogsPage from "@/pages/ClinicAuditLogsPage";
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
        path="/app/patients"
        element={
          <RoleRoute allowedRoles={["doctor", "chief_doctor", "clinic_admin"]}>
            <PatientsListPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/patients/:patientId"
        element={
          <RoleRoute allowedRoles={["doctor", "chief_doctor", "clinic_admin"]}>
            <PatientProfilePage />
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
        path="/app/ai-history"
        element={
          <RoleRoute allowedRoles={["doctor", "chief_doctor", "clinic_admin"]}>
            <AIHistoryPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/insurance-rules"
        element={
          <RoleRoute allowedRoles={["doctor", "chief_doctor", "clinic_admin"]}>
            <InsuranceRulesPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/clinic"
        element={
          <RoleRoute allowedRoles={["chief_doctor", "clinic_admin"]}>
            <ClinicDashboardPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/clinic/doctors"
        element={
          <RoleRoute allowedRoles={["clinic_admin"]}>
            <ClinicDoctorsPage />
          </RoleRoute>
        }
      />
      <Route
        path="/app/clinic/audit"
        element={
          <RoleRoute allowedRoles={["chief_doctor", "clinic_admin"]}>
            <ClinicAuditLogsPage />
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
