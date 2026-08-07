import type { Document, DocumentStatus } from "@/types/document";
import type { BackendRole, User } from "@/types/user";
import { getPrimaryBackendRole } from "@/lib/roles";

const DOCUMENT_STATUS_BY_INDEX: Record<number, Exclude<DocumentStatus, number>> = {
  0: "Draft",
  1: "Processing",
  2: "Submitted",
  3: "UnderReview",
  4: "Approved",
  5: "Rejected",
  6: "Published",
  7: "Archived",
};

function normalizeStatus(status: DocumentStatus | null | undefined): Exclude<DocumentStatus, number> | null {
  if (typeof status === "number") {
    return DOCUMENT_STATUS_BY_INDEX[status] ?? null;
  }

  return status ?? null;
}

function normalizeInstitution(value: string | null | undefined): string | null {
  return typeof value === "string" && value.trim() ? value.trim().toLowerCase() : null;
}

function normalizeDepartment(value: string | null | undefined): string | null {
  return typeof value === "string" && value.trim() ? value.trim().toLowerCase() : null;
}

function getDocumentDepartment(document: Document): string | null {
  return normalizeDepartment(document.departmentId ?? document.metadata?.departmentId ?? document.department ?? document.metadata?.department);
}

function sameInstitution(user: User, document: Document): boolean {
  const actorInstitution = normalizeInstitution(user.institutionId);
  const documentInstitution = normalizeInstitution(document.institutionId);

  return Boolean(actorInstitution && documentInstitution && actorInstitution === documentInstitution);
}

function sameDepartment(user: User, document: Document): boolean {
  const actorDepartment = normalizeDepartment(user.departmentId ?? user.department);
  const documentDepartment = getDocumentDepartment(document);

  return Boolean(actorDepartment && documentDepartment && actorDepartment === documentDepartment);
}

function isOwnedBy(user: User, document: Document): boolean {
  return Boolean(user.id && document.userId && user.id === document.userId);
}

export function getDocumentOwnerName(document: Document): string | null {
  return document.owner?.name ?? document.ownerName ?? null;
}

export function canViewDocument(user: User | null | undefined, document: Document | null | undefined): boolean {
  if (!user || !document) {
    return false;
  }

  const role = getPrimaryBackendRole(user);

  switch (role) {
    case "SystemAdmin":
      return true;
    case "InstitutionAdmin":
      return sameInstitution(user, document);
    case "Manager":
      return sameInstitution(user, document) && sameDepartment(user, document);
    case "Employee":
      return isOwnedBy(user, document);
    default:
      return false;
  }
}

export function canEditDocument(user: User | null | undefined, document: Document | null | undefined): boolean {
  if (!user || !document) {
    return false;
  }

  const role = getPrimaryBackendRole(user);
  const status = normalizeStatus(document.status);

  if (role !== "Employee") {
    return false;
  }

  return isOwnedBy(user, document) && (status === "Draft" || status === "Rejected");
}

export function canDeleteDocument(user: User | null | undefined, document: Document | null | undefined): boolean {
  if (!user || !document) {
    return false;
  }

  const status = normalizeStatus(document.status);
  if (status !== "Draft" && status !== "Rejected" && status !== "Processing") {
    return false;
  }

  const role = getPrimaryBackendRole(user);

  if (status === "Processing") {
    if (role === "SystemAdmin") {
      return true;
    }

    if (role === "InstitutionAdmin") {
      return sameInstitution(user, document);
    }
  }

  if (role === "Manager") {
    return sameInstitution(user, document) && sameDepartment(user, document);
  }

  if (role === "Employee") {
    return isOwnedBy(user, document);
  }

  return false;
}

export function canManageWorkflowReview(user: User | null | undefined, document: Document | null | undefined): boolean {
  if (!user || !document) {
    return false;
  }

  return getPrimaryBackendRole(user) === "Manager"
    && normalizeStatus(document.status) === "Submitted"
    && sameInstitution(user, document)
    && sameDepartment(user, document);
}

export function canPublishDocument(user: User | null | undefined, document: Document | null | undefined): boolean {
  if (!user || !document) {
    return false;
  }

  return getPrimaryBackendRole(user) === "InstitutionAdmin"
    && normalizeStatus(document.status) === "Approved"
    && sameInstitution(user, document);
}

export function canArchiveDocument(user: User | null | undefined, document: Document | null | undefined): boolean {
  if (!user || !document) {
    return false;
  }

  return getPrimaryBackendRole(user) === "InstitutionAdmin"
    && normalizeStatus(document.status) === "Published"
    && sameInstitution(user, document);
}

export function canTransferDocument(user: User | null | undefined, document: Document | null | undefined): boolean {
  if (!user || !document) {
    return false;
  }

  const role = getPrimaryBackendRole(user);

  if (role === "SystemAdmin") {
    return true;
  }

  if (role === "InstitutionAdmin") {
    return sameInstitution(user, document);
  }

  if (role === "Manager") {
    return sameInstitution(user, document) && sameDepartment(user, document);
  }

  return false;
}
