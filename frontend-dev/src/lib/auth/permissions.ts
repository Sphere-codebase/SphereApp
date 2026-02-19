import type { MeDTO, UserRole } from "@/types/auth";

export function canAccessAdmin(user: MeDTO | null): boolean {
  return user?.role === "platform_staff_admin";
}

export function hasRole(user: MeDTO | null, roles: UserRole | UserRole[]): boolean {
  if (!user) {
    return false;
  }
  const allowed = Array.isArray(roles) ? roles : [roles];
  return allowed.includes(user.role);
}
