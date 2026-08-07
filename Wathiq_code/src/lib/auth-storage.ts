import type { User } from "@/types/user";

export const AUTH_STORAGE_KEYS = {
  user: "user",
  token: "token",
} as const;

function safeJsonParse<T>(raw: string | null): T | null {
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function getStoredUser(): User | null {
  return safeJsonParse<User>(localStorage.getItem(AUTH_STORAGE_KEYS.user));
}

export function getStoredToken(): string | null {
  const token = localStorage.getItem(AUTH_STORAGE_KEYS.token);
  if (token) {
    return token;
  }

  const storedUser = safeJsonParse<Record<string, unknown>>(localStorage.getItem(AUTH_STORAGE_KEYS.user));
  return typeof storedUser?.token === "string" ? storedUser.token : null;
}

export function persistSession(user: User, token: string): void {
  localStorage.setItem(AUTH_STORAGE_KEYS.user, JSON.stringify(user));
  localStorage.setItem(AUTH_STORAGE_KEYS.token, token);
}

export function clearSession(): void {
  localStorage.removeItem(AUTH_STORAGE_KEYS.user);
  localStorage.removeItem(AUTH_STORAGE_KEYS.token);
}

export function updateStoredUser(patch: Partial<User>): User | null {
  const currentUser = getStoredUser();
  if (!currentUser) {
    return null;
  }

  const updatedUser: User = {
    ...currentUser,
    ...patch,
  };

  localStorage.setItem(AUTH_STORAGE_KEYS.user, JSON.stringify(updatedUser));
  return updatedUser;
}
