export type UserRole =
  | "doctor"
  | "chief_doctor"
  | "clinic_admin"
  | "platform_staff_admin";

export interface MeDTO {
  id: number;
  email: string;
  full_name?: string;
  role: UserRole;
  clinic_id: number;
  clinic_name?: string;
  is_active: boolean;
}
