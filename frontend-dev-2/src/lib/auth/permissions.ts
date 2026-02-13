import type { UserResponse } from "@/lib/api/types";

export function canAccessAdmin(user: UserResponse | null): boolean {
  return Boolean(user?.roles?.includes("admin"));
}
