export type LegacyRole = "Admin" | "Manager" | "User";
export type BackendRole = "SystemAdmin" | "InstitutionAdmin" | "Manager" | "Employee";
export type Role = LegacyRole | BackendRole;
export type UserRole = Role;

export type User = {
  id: string;
  name: string;
  email: string;
  // Keep the legacy role for the current UI until pages are migrated one-by-one.
  role: LegacyRole;
  // Store the real backend role so the structural layer can align with the API now.
  backendRole?: BackendRole | null;
  institutionId?: string | null;
  departmentId?: string | null;
  department?: string | null;
  avatar?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  isActive?: boolean | null;
  twoFactorEnabled?: boolean | null;
  failedLoginAttempts?: number | null;
  lockoutUntil?: string | null;
};

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  token: string | null;
}
