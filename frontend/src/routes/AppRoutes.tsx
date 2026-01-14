import { Navigate, Route, Routes } from "react-router-dom";

import BootstrapPage from "@/pages/BootstrapPage";
import ChatPage from "@/pages/ChatPage";
import LoginPage from "@/pages/LoginPage";
import ProtectedRoute from "@/routes/ProtectedRoute";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/bootstrap" element={<BootstrapPage />} />
      <Route
        path="/app/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
