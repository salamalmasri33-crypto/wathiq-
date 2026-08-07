import type { BackendRole, LegacyRole, User } from "@/types/user";

export type AuthApiUser = {
  id: string;
  name: string;
  email: string;
  role: BackendRole | LegacyRole;
  institutionId?: string | null;
  departmentId?: string | null;
  department?: string | null;
};

export type AuthUser = User;

export type LoginResponse =
  | { requires2FA: true; message?: string }
  | { requires2FA: false; token: string; user: AuthApiUser; message?: string };

export type Verify2FAResponse = {
  requires2FA: false;
  token: string;
  user: AuthApiUser;
  message?: string;
};

export type ForgotPasswordResponse = {
  message?: string;
};

export type ResetPasswordResponse = {
  message?: string;
};
