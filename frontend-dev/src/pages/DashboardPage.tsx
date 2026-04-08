import { useAuth } from "@/lib/auth/AuthContext";
import ClinicDashboardPage from "@/pages/ClinicDashboardPage";
import DoctorDashboardPage from "@/pages/DoctorDashboardPage";
import PlatformDashboardPage from "@/pages/PlatformDashboardPage";

export default function DashboardPage() {
  const { me } = useAuth();

  if (!me) {
    return null;
  }

  if (me.role === "platform_staff_admin") {
    return <PlatformDashboardPage />;
  }

  if (me.role === "chief_doctor" || me.role === "clinic_admin") {
    return <ClinicDashboardPage />;
  }

  return <DoctorDashboardPage />;
}
