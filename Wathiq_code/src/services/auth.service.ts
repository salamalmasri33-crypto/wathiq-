import api from "@/config/api";
import type {
  ForgotPasswordResponse,
  LoginResponse,
  ResetPasswordResponse,
  Verify2FAResponse,
} from "@/types/auth";

export type LoginCredentials = {
  email: string;
  password: string;
};

export type VerifyTwoFactorPayload = {
  email: string;
  code: string;
};

export type ResetPasswordPayload = {
  email: string;
  code: string;
  newPassword: string;
};

export async function loginRequest(payload: LoginCredentials): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>("/auth/login", payload);
  return response.data;
}

export async function verifyTwoFactorRequest(
  payload: VerifyTwoFactorPayload,
): Promise<Verify2FAResponse> {
  const response = await api.post<Verify2FAResponse>("/auth/verify-2fa", {
    Email: payload.email,
    Code: payload.code,
  });
  return response.data;
}

export async function logoutRequest(): Promise<void> {
  await api.post("/auth/logout");
}

export async function forgotPasswordRequest(email: string): Promise<ForgotPasswordResponse | string> {
  const response = await api.post<ForgotPasswordResponse | string>("/auth/password/forgot", { email });
  return response.data;
}

export async function resetPasswordRequest(
  payload: ResetPasswordPayload,
): Promise<ResetPasswordResponse | string> {
  const response = await api.post<ResetPasswordResponse | string>("/auth/password/reset", {
    Email: payload.email,
    Code: payload.code,
    NewPassword: payload.newPassword,
  });
  return response.data;
}
