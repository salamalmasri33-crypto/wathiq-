import type { BackendRole, LegacyRole, Role, User } from "@/types/user";

export const BACKEND_TO_LEGACY_ROLE: Record<BackendRole, LegacyRole> = {
  SystemAdmin: "Admin",
  InstitutionAdmin: "Admin",
  Manager: "Manager",
  Employee: "User",
};

export const LEGACY_TO_BACKEND_ROLE_CANDIDATES: Record<LegacyRole, BackendRole[]> = {
  Admin: ["SystemAdmin", "InstitutionAdmin"],
  Manager: ["Manager"],
  User: ["Employee"],
};

export const USERS_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin"];
export const REPORTS_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin", "Manager"];
export const DOCUMENTS_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin", "Manager"];
export const DASHBOARD_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin", "Manager"];
export const MY_DOCUMENTS_ALLOWED_ROLES: BackendRole[] = ["Employee"];
export const ADD_DOCUMENT_ALLOWED_ROLES: BackendRole[] = ["Manager", "Employee"];
export const EDIT_DOCUMENT_ALLOWED_ROLES: BackendRole[] = ["Employee"];
export const NOTIFICATIONS_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin", "Manager", "Employee"];
export const PERMISSIONS_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin", "Manager", "Employee"];
export const DEPARTMENTS_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin"];
export const INSTITUTION_SETTINGS_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin", "InstitutionAdmin"];
export const MAINTENANCE_ALLOWED_ROLES: BackendRole[] = ["SystemAdmin"];

export function normalizeBackendRole(role: string | null | undefined): BackendRole | null {
  switch ((role ?? "").toLowerCase()) {
    case "systemadmin":
      return "SystemAdmin";
    case "institutionadmin":
      return "InstitutionAdmin";
    case "manager":
      return "Manager";
    case "employee":
      return "Employee";
    default:
      return null;
  }
}

export function normalizeLegacyRole(role: string | null | undefined): LegacyRole | null {
  switch ((role ?? "").toLowerCase()) {
    case "admin":
      return "Admin";
    case "manager":
      return "Manager";
    case "user":
      return "User";
    default:
      return null;
  }
}

export function toLegacyRole(role: string | null | undefined): LegacyRole {
  const backendRole = normalizeBackendRole(role);
  if (backendRole) {
    return BACKEND_TO_LEGACY_ROLE[backendRole];
  }

  return normalizeLegacyRole(role) ?? "User";
}

export function createRoleBridge(role: string | null | undefined): {
  role: LegacyRole;
  backendRole: BackendRole | null;
} {
  return {
    role: toLegacyRole(role),
    backendRole: normalizeBackendRole(role),
  };
}

export function getEffectiveRoles(user: Pick<User, "role" | "backendRole"> | null | undefined): Role[] {
  if (!user) {
    return [];
  }

  const effective = new Set<Role>();

  if (user.role) {
    effective.add(user.role);
    for (const candidate of LEGACY_TO_BACKEND_ROLE_CANDIDATES[user.role]) {
      effective.add(candidate);
    }
  }

  if (user.backendRole) {
    effective.add(user.backendRole);
    effective.add(BACKEND_TO_LEGACY_ROLE[user.backendRole]);
  }

  return Array.from(effective);
}

export function getPrimaryBackendRole(
  user: Pick<User, "role" | "backendRole"> | null | undefined,
): BackendRole | null {
  if (!user) {
    return null;
  }

  if (user.backendRole) {
    return user.backendRole;
  }

  const backendRole = normalizeBackendRole(user.role);
  if (backendRole) {
    return backendRole;
  }

  const candidates = LEGACY_TO_BACKEND_ROLE_CANDIDATES[user.role as LegacyRole] ?? [];
  return candidates[0] ?? null;
}

export function getHomeRoute(user: Pick<User, "role" | "backendRole"> | null | undefined): string {
  switch (getPrimaryBackendRole(user)) {
    case "SystemAdmin":
    case "InstitutionAdmin":
    case "Manager":
      return "/dashboard";
    case "Employee":
      return "/my-documents";
    default:
      return "/login";
  }
}

export function getRolePresentation(role: string | null | undefined): { ar: string; en: string } {
  const backendRole = normalizeBackendRole(role);
  const legacyRole = normalizeLegacyRole(role);

  if (!backendRole && legacyRole === "Admin") {
    return { ar: "مدير", en: "Admin" };
  }

  switch (backendRole ?? (legacyRole === "Manager" ? "Manager" : legacyRole === "User" ? "Employee" : null)) {
    case "SystemAdmin":
      return { ar: "مدير النظام", en: "System admin" };
    case "InstitutionAdmin":
      return { ar: "مدير المؤسسة", en: "Institution admin" };
    case "Manager":
      return { ar: "مدير", en: "Manager" };
    case "Employee":
      return { ar: "موظف", en: "Employee" };
    default:
      return { ar: "مستخدم", en: "User" };
  }
}

export function hasAnyRole(
  user: Pick<User, "role" | "backendRole"> | null | undefined,
  allowedRoles?: readonly string[],
): boolean {
  if (!allowedRoles || allowedRoles.length === 0) {
    return true;
  }

  const effectiveRoles = new Set(getEffectiveRoles(user).map((role) => role.toLowerCase()));
  return allowedRoles.some((role) => effectiveRoles.has(role.toLowerCase()));
}
