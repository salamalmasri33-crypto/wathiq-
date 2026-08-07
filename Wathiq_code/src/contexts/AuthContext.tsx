import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { clearSession, getStoredToken, getStoredUser, persistSession, updateStoredUser } from "@/lib/auth-storage";
import { isDemoAuthEnabled, isDemoToken, tryDemoLogin } from "@/lib/demo-auth";
import { createRoleBridge, hasAnyRole } from "@/lib/roles";
import {
  forgotPasswordRequest,
  loginRequest,
  logoutRequest,
  resetPasswordRequest,
  verifyTwoFactorRequest,
} from "@/services/auth.service";
import type { AuthApiUser } from "@/types/auth";
import type { AuthState, User } from "@/types/user";

type LoginResult = "ok" | "2fa" | "fail";

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<LoginResult>;
  verify2fa: (email: string, code: string) => Promise<boolean>;
  updateLocalUser: (patch: Partial<User>) => void;
  requires2fa: boolean;
  pending2faEmail?: string;
  logout: () => Promise<void>;
  checkPermission: (allowedRoles: string[]) => boolean;
  forgotPassword: (email: string) => Promise<string>;
  resetPassword: (email: string, code: string, newPassword: string) => Promise<string>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function extractMessage(data: unknown): string | null {
  if (typeof data === "string") {
    return data;
  }

  if (isRecord(data) && typeof data.message === "string") {
    return data.message;
  }

  return null;
}

function normalizeAuthUser(rawUser: AuthApiUser): User {
  const roleBridge = createRoleBridge(rawUser.role);

  return {
    id: rawUser.id,
    name: rawUser.name,
    email: rawUser.email,
    role: roleBridge.role,
    backendRole: roleBridge.backendRole,
    institutionId: rawUser.institutionId ?? null,
    departmentId: rawUser.departmentId ?? null,
    department: rawUser.department ?? null,
  };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true,
  });
  const [requires2fa, setRequires2fa] = useState(false);
  const [pending2faEmail, setPending2faEmail] = useState<string | undefined>(undefined);

  useEffect(() => {
    const storedUser = getStoredUser();
    const storedToken = getStoredToken();

    if (!isDemoAuthEnabled() && isDemoToken(storedToken)) {
      clearSession();
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
      });
      return;
    }

    setAuthState({
      user: storedUser,
      token: storedToken,
      isAuthenticated: Boolean(storedUser && storedToken),
      isLoading: false,
    });
  }, []);

  const updateLocalUser = (patch: Partial<User>) => {
    setAuthState((prev) => {
      if (!prev.user) {
        return prev;
      }

      const updatedUser = updateStoredUser(patch);
      if (!updatedUser) {
        return prev;
      }

      return {
        ...prev,
        user: updatedUser,
      };
    });
  };

  const completeAuthentication = (rawUser: AuthApiUser, token: string) => {
    const normalizedUser = normalizeAuthUser(rawUser);
    persistSession(normalizedUser, token);

    setAuthState({
      user: normalizedUser,
      token,
      isAuthenticated: true,
      isLoading: false,
    });

    setRequires2fa(false);
    setPending2faEmail(undefined);
  };

  const login = async (email: string, password: string): Promise<LoginResult> => {
    const demoSession = tryDemoLogin(email, password);
    if (demoSession) {
      completeAuthentication(demoSession.user, demoSession.token);
      return "ok";
    }

    try {
      const response = await loginRequest({ email, password });

      if (response.requires2FA) {
        setRequires2fa(true);
        setPending2faEmail(email);
        return "2fa";
      }

      if (response.requires2FA === false) completeAuthentication(response.user, response.token);
      return "ok";
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        console.error("Login failed:", extractMessage(error.response?.data) ?? error.message);
      } else {
        console.error("Login failed:", String(error));
      }

      return "fail";
    }
  };

  const verify2fa = async (email: string, code: string): Promise<boolean> => {
    try {
      const response = await verifyTwoFactorRequest({ email, code });
      completeAuthentication(response.user, response.token);
      return true;
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        console.error("Verify 2FA failed:", extractMessage(error.response?.data) ?? error.message);
      } else {
        console.error("Verify 2FA failed:", String(error));
      }

      return false;
    }
  };

  const logout = async (): Promise<void> => {
    try {
      if (authState.token) {
        await logoutRequest();
      }
    } catch (error: unknown) {
      if (axios.isAxiosError(error)) {
        console.error("Logout failed:", extractMessage(error.response?.data) ?? error.message);
      } else {
        console.error("Logout failed:", String(error));
      }
    } finally {
      clearSession();
      setAuthState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
      });
      setRequires2fa(false);
      setPending2faEmail(undefined);
    }
  };

  const checkPermission = (allowedRoles: string[]): boolean => {
    return hasAnyRole(authState.user, allowedRoles);
  };

  const forgotPassword = async (email: string): Promise<string> => {
    const response = await forgotPasswordRequest(email);
    return extractMessage(response) ?? "Request sent";
  };

  const resetPassword = async (
    email: string,
    code: string,
    newPassword: string,
  ): Promise<string> => {
    const response = await resetPasswordRequest({ email, code, newPassword });
    return extractMessage(response) ?? "Password reset";
  };

  const value = useMemo<AuthContextType>(
    () => ({
      ...authState,
      login,
      verify2fa,
      updateLocalUser,
      requires2fa,
      pending2faEmail,
      logout,
      checkPermission,
      forgotPassword,
      resetPassword,
    }),
    [authState, requires2fa, pending2faEmail],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
