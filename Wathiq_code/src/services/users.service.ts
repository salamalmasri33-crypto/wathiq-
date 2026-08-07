import api from "@/config/api";
import type { AddUserDto, UpdateUserDto } from "@/types/dto";

export type UpdateProfileDto = {
  name: string;
  email: string;
};

export type ChangePasswordDto = {
  currentPassword: string;
  newPassword: string;
};

export type TwoFactorToggleDto = {
  enabled: boolean;
};

export type CreateAdminDto = {
  name: string;
  email: string;
  password: string;
};

export async function getUsersRequest(params?: {
  role?: string;
  search?: string;
}): Promise<unknown> {
  const response = await api.get("/users", { params });
  return response.data;
}

export async function addUserRequest(payload: AddUserDto): Promise<unknown> {
  const response = await api.post("/users/add", payload);
  return response.data;
}

export async function createAdminRequest(payload: CreateAdminDto): Promise<unknown> {
  const response = await api.post("/users/create-admin", payload);
  return response.data;
}

export async function editUserRequest(userId: string, payload: UpdateUserDto): Promise<unknown> {
  const response = await api.put(`/users/edit/${userId}`, payload);
  return response.data;
}

export async function assignRoleRequest(userId: string, role: string): Promise<unknown> {
  const response = await api.put(`/users/${userId}/assign-role`, { role });
  return response.data;
}

export async function deleteUserRequest(userId: string): Promise<unknown> {
  const response = await api.delete(`/users/${userId}`);
  return response.data;
}

export async function updateProfileRequest(payload: UpdateProfileDto): Promise<unknown> {
  const response = await api.put("/users/profile", payload);
  return response.data;
}

export async function changePasswordRequest(payload: ChangePasswordDto): Promise<unknown> {
  const response = await api.put("/users/change-password", payload);
  return response.data;
}

export async function getTwoFactorStatusRequest(): Promise<{ enabled: boolean }> {
  const response = await api.get<{ enabled: boolean }>("/users/2fa");
  return response.data;
}

export async function setTwoFactorStatusRequest(payload: TwoFactorToggleDto): Promise<unknown> {
  const response = await api.put("/users/2fa", payload);
  return response.data;
}
