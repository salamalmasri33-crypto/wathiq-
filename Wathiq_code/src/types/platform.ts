import type { BackendRole } from "@/types/user";
import type { DocumentStatus } from "@/types/document";

export type Department = {
  id: string;
  name: string;
  institutionId?: string | null;
  parentDepartmentId?: string | null;
  parentDepartmentName?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type DepartmentTreeNode = Department & {
  children?: DepartmentTreeNode[];
};

export type NotificationItem = {
  id: string;
  userId?: string | null;
  documentId?: string | null;
  institutionId?: string | null;
  type?: string | null;
  title?: string | null;
  message?: string | null;
  isRead?: boolean;
  createdAt?: string | null;
  readAt?: string | null;
};

export type NotificationsQuery = {
  unreadOnly?: boolean;
  page?: number;
  pageSize?: number;
};

export type NotificationsPage = {
  total: number;
  unreadCount: number;
  page: number;
  pageSize: number;
  data: NotificationItem[];
};

export type UnreadNotificationsResponse = {
  unreadCount: number;
};

export type PermissionCoverage = Record<string, unknown>;
export type PermissionScope = Record<string, unknown> & {
  role?: BackendRole | null;
  institutionId?: string | null;
  departmentId?: string | null;
};

export type DocumentAccessReview = {
  documentId: string;
  ownerUserId?: string | null;
  institutionId?: string | null;
  departmentId?: string | null;
  department?: string | null;
  status?: DocumentStatus | null;
  canView: boolean;
  canEdit: boolean;
  canDelete: boolean;
  canSubmit: boolean;
  canStartReview: boolean;
  canApprove: boolean;
  canReject: boolean;
  canPublish: boolean;
  canArchive: boolean;
};

export type InstitutionSettings = {
  institutionId?: string | null;
  institutionName?: string | null;
  description?: string | null;
  contactEmail?: string | null;
  timeZone?: string | null;
  defaultLanguage?: string | null;
  brandingPrimaryColor?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type UpdateInstitutionSettingsDto = {
  institutionId?: string | null;
  institutionName?: string | null;
  description?: string | null;
  contactEmail?: string | null;
  timeZone?: string | null;
  defaultLanguage?: string | null;
  brandingPrimaryColor?: string | null;
};

export type AuditLog = {
  timestamp?: string | null;
  userId?: string | null;
  userName?: string | null;
  userEmail?: string | null;
  userRole?: string | null;
  action?: string | null;
  documentId?: string | null;
  description?: string | null;
};
