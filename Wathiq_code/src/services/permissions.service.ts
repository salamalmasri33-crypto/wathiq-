import api from "@/config/api";
import type { DocumentAccessReview, PermissionCoverage, PermissionScope } from "@/types/platform";

export async function getPermissionsCoverageRequest(): Promise<PermissionCoverage> {
  const response = await api.get<PermissionCoverage>("/permissions/coverage");
  return response.data;
}

export async function getMyScopeRequest(): Promise<PermissionScope> {
  const response = await api.get<PermissionScope>("/permissions/me");
  return response.data;
}

export async function getDocumentAccessRequest(documentId: string): Promise<DocumentAccessReview> {
  const response = await api.get<DocumentAccessReview>(`/permissions/documents/${documentId}`);
  return response.data;
}
